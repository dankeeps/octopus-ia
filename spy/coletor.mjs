// Coletor do Spy: pesquisa a Biblioteca de Anúncios da Meta num Chromium próprio (Playwright)
// e devolve o que achou, uma linha JSON por evento, no stdout.
//
// Quem roda é o servidor do Octopus IA (spy.py). A primeira linha do stdin diz o que fazer:
//   {"acao":"buscar","consulta":{palavras,pais,min_anuncios,min_dias,max_bibliotecas},"monitoradas":[{pagina,link}]}
//   {"acao":"abrir"}                         só abre o navegador (para entrar no Facebook, aceitar aviso…)
// As linhas seguintes são comandos: {"cmd":"continuar"} {"cmd":"navegador"} {"cmd":"parar"}
// Eventos no stdout: progresso · resultado · acao (precisa da pessoa) · fim · erro
import { existsSync } from 'node:fs';
import { mkdir, readdir } from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// os dados do Spy (perfil do navegador e o próprio navegador) ficam na pasta de dados do aplicativo, que o servidor passa em OCTOPUS_DADOS
const PASTA = path.join(process.env.OCTOPUS_DADOS || path.join(RAIZ, '.local'), 'spy');
const NAVEGADORES = path.join(PASTA, 'browsers');
const PERFIL = path.join(PASTA, 'perfil');
process.env.PLAYWRIGHT_BROWSERS_PATH ??= NAVEGADORES;

const BUSCA_PLACEHOLDER = 'Pesquisar por palavra-chave ou anunciante';
const MESES = { jan: 0, fev: 1, mar: 2, abr: 3, mai: 4, jun: 5, jul: 6, ago: 7, set: 8, out: 9, nov: 10, dez: 11 };
const MARCAS = /resultados|Nenhum an[uú]ncio corresponde|Identifica[cç][aã]o da biblioteca/i;
const PRECISA = 'A Meta não mostrou os resultados. Abra o navegador do Spy, resolva o aviso (login, cookies ou verificação) e clique em Continuar.';
const CANDIDATOS = 40;      // anúncios lidos por palavra antes de parar de rolar
const ROLAGENS = 6;
const PROVAS = 6;           // anúncios guardados como prova por página

const emitir = (o) => process.stdout.write(JSON.stringify(o) + '\n');

function urlBusca(palavra, pais) {
  const p = new URLSearchParams({ active_status: 'active', ad_type: 'all', country: pais, is_targeted_country: 'false',
    media_type: 'video', q: palavra.replace(/\s*\+\s*/g, '+'),
    // "emagrecer+truque" é combo: todas as palavras no anúncio, em qualquer ordem (é como a própria biblioteca faz com o +).
    // Sem o +, continua a expressão exata ("truque do limão" só acha esse trecho, nessa ordem)
    search_type: /\+/.test(palavra) ? 'keyword_unordered' : 'keyword_exact_phrase' });      // só anúncio em vídeo
  p.set('sort_data[mode]', 'total_impressions');
  p.set('sort_data[direction]', 'desc');
  return 'https://www.facebook.com/ads/library/?' + p.toString();
}
// a biblioteca de uma página, só com os anúncios ativos em vídeo (imagem não entra na conta)
function urlPagina(pid, pais) {
  return 'https://www.facebook.com/ads/library/?' + new URLSearchParams({ active_status: 'active', ad_type: 'all', country: pais,
    is_targeted_country: 'false', media_type: 'video', search_type: 'page', view_all_page_id: pid }).toString();
}
function soVideo(link) {
  try { const u = new URL(link); if (!/facebook\.com$/.test(u.hostname) || !u.searchParams.get('view_all_page_id')) return link; u.searchParams.set('media_type', 'video'); return u.toString(); }
  catch { return link; }
}
const mesmoNome = (a, b) => { const n = (x) => x.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); return n(a) === n(b); };
function data(texto) {
  const m = texto.match(/(\d{1,2}) de ([a-zç]{3})\.? de (\d{4})/i);
  if (!m) return null;
  const mes = MESES[m[2].toLowerCase().slice(0, 3)];
  return mes === undefined ? null : new Date(Date.UTC(Number(m[3]), mes, Number(m[1])));
}
function lerAnuncios(texto) {
  const pedacos = texto.split(/\nAtivo\nIdentifica[cç][aã]o da biblioteca: /).slice(1);
  const lista = [];
  for (const p of pedacos) {
    const cab = p.match(/^(\d+)\nVeicula[cç][aã]o iniciada em ([^\n]+)\n/);
    if (!cab) continue;
    const d = data(cab[2]);
    const nome = p.match(/\n([^\n]{1,120})\nPatrocinado\n/);
    if (!nome) continue;
    const depois = p.slice((nome.index ?? 0) + nome[0].length);
    const copy = depois.split(/\n\d:\d\d\s*\/\s*\d:\d\d/)[0]?.trim().slice(0, 600);
    lista.push({
      id: cab[1],
      inicio: d ? d.toISOString().slice(0, 10) : null,
      dias: d ? Math.max(0, Math.floor((Date.now() - d.getTime()) / 86_400_000)) : null,
      anunciante: nome[1].trim(),
      ...(copy ? { texto: copy } : {}),
    });
  }
  return lista;
}
function contagem(texto) {
  if (/Nenhum an[uú]ncio corresponde/i.test(texto)) return 0;
  const m = texto.match(/~?\s*([\d.,]+)\s+resultados?/i);
  if (!m) return null;
  const n = m[1].replace(/[^\d]/g, '');
  return n ? Number(n) : null;
}
const prova = (a, busca) => ({ ...(busca === true ? { busca: true } : {}), id: a.id, inicio: a.inicio, dias: a.dias, link: 'https://www.facebook.com/ads/library/?id=' + a.id, ...(a.texto ? { texto: a.texto } : {}) });

// ---------- navegador: um perfil só, sem rodar visível e invisível ao mesmo tempo ----------
let pw = null, contexto = null, modo = null, parado = false, esperando = [];
async function garantir(alvo) {
  if (!pw) pw = await import('playwright');
  if (contexto && modo === alvo) return contexto;
  if (contexto) { const velho = contexto; contexto = null; modo = null; await velho.close().catch(() => {}); }
  await mkdir(PERFIL, { recursive: true, mode: 0o700 });
  contexto = await pw.chromium.launchPersistentContext(PERFIL, {
    headless: alvo === 'invisivel', channel: 'chromium', locale: 'pt-BR', viewport: { width: 1400, height: 1000 },
  });
  modo = alvo;
  return contexto;
}
// a Meta manda, junto de cada anúncio da busca, o id da página que anuncia: guardamos para abrir a biblioteca certa, sem depender do nome
const PAGINA_DO_ANUNCIO = new Map();
function guardarIds(txt) {
  for (const m of txt.matchAll(/"ad_archive_id":"(\d+)"/g)) {
    const pid = (txt.slice(m.index, m.index + 3000).match(/"page_id":"(\d+)"/) || [])[1];
    if (pid) PAGINA_DO_ANUNCIO.set(m[1], pid);
  }
}
const ouvindo = new WeakSet();
async function pagina() {
  const ctx = await garantir('invisivel');
  const p = ctx.pages()[0] || (await ctx.newPage());
  if (!ouvindo.has(p)) {
    ouvindo.add(p);
    p.on('response', async (r) => {                 // os anúncios que chegam ao rolar a página
      if (!r.url().includes('/api/graphql')) return;
      const t = await r.text().catch(() => '');
      if (t.includes('ad_archive_id')) guardarIds(t);
    });
  }
  return p;
}
async function abrirVisivel(url) {
  const ctx = await garantir('visivel');
  const p = ctx.pages()[0] || (await ctx.newPage());
  await p.bringToFront().catch(() => {});
  if (url || p.url() === 'about:blank') await p.goto(url || 'https://www.facebook.com/ads/library/', { waitUntil: 'domcontentloaded' }).catch(() => {});
  return ctx;
}
const liberar = () => { const w = esperando; esperando = []; w.forEach((f) => f()); };
const esperarContinuar = () => new Promise((r) => { if (parado) return r(); esperando.push(r); });
function checar() { if (parado) throw new Error('parado'); }

async function esperarMarcas(p) {
  const limite = Date.now() + 15000;
  while (Date.now() < limite) {
    if (parado) return '';
    const t = await p.evaluate(() => document.body.innerText).catch(() => '');
    if (MARCAS.test(t)) return t;
    await p.waitForTimeout(700);
  }
  return null;
}
// abre uma URL e espera a Meta mostrar resultados; se não mostrar, pede a pessoa e tenta de novo
let urlAtual = '';
async function carregar(url) {
  for (let tentativa = 0; tentativa < 2 && !parado; tentativa++) {
    urlAtual = url;
    const p = await pagina();
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    const t = await esperarMarcas(p);
    if (t !== null) return { p, t };
    if (parado) break;
    emitir({ tipo: 'acao', mensagem: PRECISA });
    await esperarContinuar();
  }
  return { p: await pagina(), t: '' };
}
// abre a biblioteca da página pelo id (só vídeos ativos) e lê a contagem e os anúncios de prova
async function porId(pid, nome, pais) {
  const ctx = await garantir('invisivel');
  const p = await ctx.newPage();
  try {
    await p.goto(urlPagina(pid, pais), { waitUntil: 'domcontentloaded', timeout: 45000 });
    const t = await esperarMarcas(p);
    if (!t) return null;
    await p.waitForTimeout(800);
    const t2 = await p.evaluate(() => document.body.innerText).catch(() => t);
    return { page_id: pid, link: urlPagina(pid, pais), texto_contagem: t2.match(/~?\s*[\d.,]+\s+resultados?/i)?.[0] || null,
      anuncios: contagem(t2), provas: lerAnuncios(t2).slice(0, PROVAS).map((x) => prova(x)) };
  } catch {
    return null;
  } finally {
    await p.close().catch(() => {});
  }
}

// reserva, quando a Meta não mandou o id: acha a biblioteca da página pela própria busca da Meta (sugestão de anunciante) e lê a contagem
async function resolver(nome, palavra, pais) {
  const ctx = await garantir('invisivel');
  const p = await ctx.newPage();
  try {
    await p.goto(urlBusca(palavra, pais), { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(2500);
    const caixa = p.getByPlaceholder(BUSCA_PLACEHOLDER);
    await caixa.click({ timeout: 10000 });
    await caixa.fill('');
    await caixa.type(nome, { delay: 40 });
    await p.waitForTimeout(1800);
    await p.keyboard.press('ArrowDown');
    await p.keyboard.press('ArrowDown');
    await p.keyboard.press('Enter');
    await p.waitForTimeout(3500);
    const m = p.url().match(/view_all_page_id=(\d+)/);
    if (!m) return null;
    // a sugestão da Meta pode cair numa página de nome parecido: só vale se os anúncios forem mesmo deste anunciante
    const achados = lerAnuncios(await p.evaluate(() => document.body.innerText).catch(() => ''));
    if (achados.length && !achados.some((x) => mesmoNome(x.anunciante, nome))) return null;
    // a contagem e os anúncios de prova são só dos vídeos
    await p.goto(urlPagina(m[1], pais), { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(3500);
    const t = await p.evaluate(() => document.body.innerText).catch(() => '');
    if (!MARCAS.test(t)) return null;
    return { page_id: m[1], link: urlPagina(m[1], pais), texto_contagem: t.match(/~?\s*[\d.,]+\s+resultados?/i)?.[0] || null,
      anuncios: contagem(t), provas: lerAnuncios(t).filter((x) => mesmoNome(x.anunciante, nome)).slice(0, PROVAS).map((x) => prova(x)) };
  } catch {
    return null;
  } finally {
    await p.close().catch(() => {});
  }
}

function avaliar(ativos, provas, c) {
  const temAntigo = provas.some((a) => a.dias !== null && a.dias >= c.min_dias);
  return ativos === null ? null : ativos >= c.min_anuncios && temAntigo;
}

async function buscar(c, monitoradas, pular = []) {
  const palavras = c.palavras;
  // bibliotecas já monitoradas que a pessoa não quer ver na busca: não contam para o limite e saem marcadas
  const pularId = new Set(pular.map((x) => String(x.page_id || '')).filter(Boolean)), pularNome = new Set(pular.map((x) => String(x.pagina || '').toLowerCase()).filter(Boolean));
  const vistos = new Map();
  let confirmadas = 0, conferidos = 0;
  emitir({ tipo: 'progresso', palavras_total: palavras.length, palavras_feitas: 0, monitoradas_total: monitoradas.length });

  // 1. monitoradas: conferidas sempre, mesmo que a busca não as traga
  for (let i = 0; i < monitoradas.length; i++) {
    checar();
    const m = monitoradas[i];
    emitir({ tipo: 'progresso', atual: 'monitorada: ' + m.pagina });
    const { t } = await carregar(soVideo(m.link));
    checar();
    const provas = lerAnuncios(t).slice(0, PROVAS).map((x) => prova(x));
    const ativos = t ? contagem(t) : null;
    const pid = (m.link.match(/view_all_page_id=(\d+)/) || [])[1] || '';
    const r = { id: pid || m.pagina, pagina: m.pagina, page_id: pid, link: m.link, pais: c.pais, anuncios: ativos,
      texto_contagem: t.match(/~?\s*[\d.,]+\s+resultados?/i)?.[0] || null, provas, palavras: [], monitorada: true,
      confere: avaliar(ativos, provas, c), motivo: ativos === null ? 'Não deu para ler a contagem desta biblioteca.' : 'Monitorada.',
      parcial: ativos === null, coletado: Date.now() };
    vistos.set(m.pagina.toLowerCase(), r);
    emitir({ tipo: 'resultado', r });
    emitir({ tipo: 'progresso', monitoradas_feitas: i + 1 });
  }

  // 2. palavras-chave
  for (let k = 0; k < palavras.length && confirmadas < c.max_bibliotecas; k++) {
    checar();
    const palavra = palavras[k];
    emitir({ tipo: 'progresso', atual: palavra });
    let { p, t } = await carregar(urlBusca(palavra, c.pais));
    checar();
    let anuncios = lerAnuncios(t);
    guardarIds(await p.content().catch(() => ''));
    for (let r = 0; r < ROLAGENS && anuncios.length < CANDIDATOS && t; r++) {
      checar();
      const antes = anuncios.length;
      await p.mouse.wheel(0, 4000).catch(() => {});
      await p.waitForTimeout(1200);
      t = await p.evaluate(() => document.body.innerText).catch(() => t);
      anuncios = lerAnuncios(t);
      if (anuncios.length === antes) break;
    }
    for (const a of anuncios) {
      checar();
      if (confirmadas >= c.max_bibliotecas) break;
      const chave = a.anunciante.toLowerCase();
      const visto = vistos.get(chave);
      if (visto) {
        if (!visto.palavras.includes(palavra)) { visto.palavras.push(palavra); emitir({ tipo: 'resultado', r: visto }); }
        continue;
      }
      const pid = PAGINA_DO_ANUNCIO.get(a.id);
      if (pularNome.has(chave) || (pid && pularId.has(String(pid)))) {
        const r = { id: pid || a.anunciante, pagina: a.anunciante, page_id: pid || '', link: pid ? urlPagina(pid, c.pais) : 'https://www.facebook.com/ads/library/?id=' + a.id,
          pais: c.pais, anuncios: null, texto_contagem: null, provas: [prova(a, true)], palavras: [palavra], monitorada: false, ja_monitorada: true, confere: null,
          motivo: 'Já está nas suas bibliotecas monitoradas.', parcial: true, coletado: Date.now() };
        vistos.set(chave, r); emitir({ tipo: 'resultado', r }); continue;
      }
      conferidos++;
      emitir({ tipo: 'progresso', conferidos });
      const o = (pid && await porId(pid, a.anunciante, c.pais)) || await resolver(a.anunciante, palavra, c.pais);
      checar();
      const provas = [prova(a, true), ...(o?.provas || []).filter((x) => x.id !== a.id)].slice(0, PROVAS);
      const ativos = o?.anuncios ?? null;
      const confere = avaliar(ativos, provas, c);
      const r = { id: o?.page_id || a.anunciante, pagina: a.anunciante, page_id: o?.page_id || '',
        link: o?.link || 'https://www.facebook.com/ads/library/?id=' + a.id, pais: c.pais, anuncios: ativos,
        texto_contagem: o?.texto_contagem || null, provas, palavras: [palavra], monitorada: false, confere,
        motivo: !o ? 'Não deu para abrir a biblioteca deste anunciante sozinho.' : confere ? 'Passa nos filtros.' : 'Não passa em todos os filtros.',
        parcial: !o, coletado: Date.now() };
      if (r.page_id && pularId.has(String(r.page_id))) r.ja_monitorada = true;
      vistos.set(chave, r);
      emitir({ tipo: 'resultado', r });
      if (confere === true && !r.ja_monitorada) confirmadas++;
    }
    emitir({ tipo: 'progresso', palavras_feitas: k + 1 });
  }
}

// abre o link de uma biblioteca (ou de um anúncio) e devolve página, page_id, contagem e anúncios
async function verificar(link, pais) {
  const p = await pagina();
  link = soVideo(link);
  await p.goto(link, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
  const t = await esperarMarcas(p);
  if (!t) throw new Error('A Meta não mostrou a biblioteca. Abra o navegador do Spy, resolva o aviso e tente de novo.');
  const anuncios = lerAnuncios(t);
  let pid = (p.url().match(/view_all_page_id=(\d+)/) || link.match(/view_all_page_id=(\d+)/) || [])[1] || '';
  let nome = anuncios[0]?.anunciante || '';
  if (!nome) throw new Error('Não achei anúncios ativos nesse link. Confira se é o link da biblioteca da página.');
  if (!pid) {
    // link de um anúncio só: acha a biblioteca da página pelo nome
    const o = await resolver(nome, nome, pais);
    if (!o) throw new Error('Achei o anúncio, mas não a biblioteca da página. Use o link com view_all_page_id.');
    return { pagina: nome, page_id: o.page_id, link: o.link, anuncios: o.anuncios, provas: o.provas, texto_contagem: o.texto_contagem };
  }
  return { pagina: nome, page_id: pid, link: p.url().includes('view_all_page_id') ? p.url() : link, anuncios: contagem(t),
    provas: anuncios.slice(0, PROVAS).map((x) => prova(x)), texto_contagem: t.match(/~?\s*[\d.,]+\s+resultados?/i)?.[0] || null };
}

async function instalado() {
  try {
    return (await readdir(NAVEGADORES)).some((n) => n.startsWith('chromium-') && existsSync(path.join(NAVEGADORES, n, 'INSTALLATION_COMPLETE')));
  } catch { return false; }
}

async function encerrar(codigo = 0) {
  const c = contexto; contexto = null;
  await c?.close().catch(() => {});
  process.exit(codigo);
}

const entrada = readline.createInterface({ input: process.stdin });
let pedido = null;
entrada.on('line', async (linha) => {
  let msg;
  try { msg = JSON.parse(linha); } catch { return; }
  if (!pedido) { pedido = msg; return iniciar(msg); }
  if (msg.cmd === 'parar') { parado = true; liberar(); if (pedido.acao === 'abrir') encerrar(0); }
  else if (msg.cmd === 'navegador') { try { await abrirVisivel(urlAtual); emitir({ tipo: 'navegador', aberto: true }); } catch (e) { emitir({ tipo: 'erro', mensagem: String(e.message || e) }); } }
  else if (msg.cmd === 'continuar') { try { await garantir('invisivel'); } catch {} liberar(); }
});
entrada.on('close', () => { parado = true; liberar(); if (pedido?.acao === 'abrir') encerrar(0); });

async function iniciar(msg) {
  if (!(await instalado())) { emitir({ tipo: 'erro', mensagem: 'O navegador do Spy não está instalado. Peça ao Claude Code ou ao Codex para rodar a instalação do Octopus IA de novo.' }); return encerrar(1); }
  try {
    if (msg.acao === 'abrir') {
      const ctx = await abrirVisivel(msg.url);
      emitir({ tipo: 'navegador', aberto: true });
      ctx.on('close', () => { emitir({ tipo: 'fim' }); process.exit(0); });
      return;
    }
    if (msg.acao === 'verificar') { emitir({ tipo: 'verificado', r: await verificar(msg.link, msg.pais || 'BR') }); }
    else await buscar(msg.consulta, msg.monitoradas || [], msg.pular || []);
    emitir({ tipo: 'fim' });
  } catch (e) {
    if (parado) emitir({ tipo: 'fim', parado: true });
    else emitir({ tipo: 'erro', mensagem: String(e?.message || e).slice(0, 400) });
  }
  await encerrar(0);
}
