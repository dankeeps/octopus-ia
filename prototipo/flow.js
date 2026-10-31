/* Canvas de flows do Octopus IA (React Flow). Monta dentro da página vanilla e conversa com ela por AtlasFlow.
   O estado do flow (nós, ligações, posição da câmera) vive no objeto `flow` que a página guarda; a conversa
   de cada nó é desenhada pela página no painel lateral. */

(function () {
  const RF = window.ReactFlow;
  const { ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Handle, Position, addEdge,
    useNodesState, useEdgesState, useReactFlow, useViewport, Panel, BaseEdge, EdgeLabelRenderer, getBezierPath, NodeResizeControl } = RF;
  const { useState, useEffect, useCallback, useRef } = React;
  const html = htm.bind(React.createElement);

  /* ---------- ícones (traço fino, dentro de círculo) ---------- */
  const PATHS = {
    biblia: html`<path d="M12 6.5C10.3 5.2 7.9 4.5 4.5 4.5v13c3.4 0 5.8.7 7.5 2 1.7-1.3 4.1-2 7.5-2v-13c-3.4 0-5.8.7-7.5 2z"/><path d="M12 6.5v13"/>`,
    briefing: html`<rect x="5.5" y="4.5" width="13" height="16" rx="2.5"/><path d="M9.5 4.5V3.8a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v.7"/><path d="M8.8 10.5h6.4M8.8 13.5h6.4M8.8 16.5h3.8"/>`,
    blocos: html`<rect x="4" y="4" width="16" height="4.5" rx="1.5"/><rect x="4" y="10" width="16" height="4.5" rx="1.5"/><rect x="4" y="16" width="10" height="4" rx="1.5"/>`,
    inteligencia: html`<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>`,
    chat: html`<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M8 12h.01M12 12h.01M16 12h.01" stroke-width="2.4"/>`,
    chatgpt: html`<path fill="currentColor" stroke="none" d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/>`,
    mais: html`<path d="M12 5v14M5 12h14"/>`,
    menos: html`<path d="M5 12h14"/>`,
    ajustar: html`<path d="M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15"/>`,
    arquivo: html`<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10.5A.5.5 0 0 1 6.5 20V4a.5.5 0 0 1 .5-.5z"/><path d="M14 3.5V8h4"/>`,
    imagem: html`<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="m20.5 16-5-5-8.5 8.5"/>`,
    x: html`<path d="M6 6l12 12M18 6 6 18"/>`,
    nota: html`<path d="M5 4.500h14a1 1 0 0 1 1 1V14l-5.500 5.500H5a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1z"/><path d="M14.500 19.500V15a1 1 0 0 1 1-1H20M8 9h8M8 12.500h4"/>`,
    selecao: html`<path d="M4 8V5.500A1.500 1.500 0 0 1 5.500 4H8M12 4h3M19 4h.500A1.500 1.500 0 0 1 21 5.500V8M4 12v3M4 19v.500A1.500 1.500 0 0 0 5.500 21H8"/><path d="M12.500 12.500l8 3-3.300 1.400-1.400 3.300z" fill="currentColor"/>`,
    guia: html`<circle cx="12" cy="12" r="8.500"/><path d="M12 11v5.500"/><path d="M12 7.800h.01" stroke-width="2.400"/>`,
    pasta: html`<path d="M3.5 7.5a2 2 0 0 1 2-2h3.6l2 2.2h7.4a2 2 0 0 1 2 2v7.8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>`,
    youtube: html`<rect x="3" y="6" width="18" height="12" rx="3.5"/><path d="M10.5 9.6v4.8l4-2.4z" fill="currentColor" stroke="none"/>`,
    parar: html`<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none"/>`,
    mic: html`<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/>`,
    asterisco: html`<path d="M12 4.5v15M5.5 8.2l13 7.6M18.5 8.2l-13 7.6"/>`,
    oferta: html`<path d="M3.5 7.5A2 2 0 0 1 5.5 5.5h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M9 13.5l2 2 4-4"/>`,
    grupo: html`<rect x="3.5" y="5.5" width="17" height="13" rx="3" stroke-dasharray="3 2.4"/><path d="M7.5 9.5h4M7.5 13h7"/>`,
    transcricao: html`<path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/>`,
    maximizar: html`<path d="M14 4h6v6M10 20H4v-6M20 4l-6.5 6.5M4 20l6.5-6.5"/>`,
    minimizar: html`<path d="M4 14h6v6M20 10h-6V4M10 14l-6.5 6.5M14 10l6.5-6.5"/>`,
    olho: html`<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>`,
    pontos: html`<circle cx="5.5" cy="12" r="1.3" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.3" fill="currentColor" stroke="none"/>`,
    lixo: html`<path d="M4.5 7h15M10 11v6M14 11v6M6.5 7l1 13h9l1-13M9.5 7V4.5h5V7"/>`,
    upload: html`<path d="M12 16V4M7 9l5-5 5 5M4.5 15.5v3a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-3"/>`,
    video: html`<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10.3 9.3v5.4l4.6-2.7z"/>`,
    social: html`<path d="M10 13.500a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1"/><path d="M14 10.500a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1"/>`,
    lapis: html`<path d="M14.5 5.5l4 4M4.5 19.5l1-4.5L15.8 4.7a1.4 1.4 0 0 1 2 0l1.5 1.5a1.4 1.4 0 0 1 0 2L9 18.5z"/>`,
    abrir: html`<path d="M7 17 17 7M9 7h8v8"/>`,
    enviar: html`<path d="M12 19V5M6 11l6-6 6 6"/>`,
    memoria: html`<path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.5"/><path d="M4 4v4.5h4.5M12 8v4.5l3 2"/>`,
    limpar: html`<path d="M4.5 7h15M10 11v6M14 11v6M6.5 7l1 13h9l1-13M9.5 7V4.5h5V7"/>`,
    cofre: html`<path fill="currentColor" stroke="none" d="M19.355 18.538a68.967 68.959 0 0 0 1.858-2.954.81.81 0 0 0-.062-.9c-.516-.685-1.504-2.075-2.042-3.362-.553-1.321-.636-3.375-.64-4.377a1.707 1.707 0 0 0-.358-1.05l-3.198-4.064a3.744 3.744 0 0 1-.076.543c-.106.503-.307 1.004-.536 1.5-.134.29-.29.6-.446.914l-.31.626c-.516 1.068-.997 2.227-1.132 3.59-.124 1.26.046 2.73.815 4.481.128.011.257.025.386.044a6.363 6.363 0 0 1 3.326 1.505c.916.79 1.744 1.922 2.415 3.5zM8.199 22.569c.073.012.146.02.22.02.78.024 2.095.092 3.16.29.87.16 2.593.64 4.01 1.055 1.083.316 2.198-.548 2.355-1.664.114-.814.33-1.735.725-2.58l-.01.005c-.67-1.87-1.522-3.078-2.416-3.849a5.295 5.295 0 0 0-2.778-1.257c-1.54-.216-2.952.19-3.84.45.532 2.218.368 4.829-1.425 7.531zM5.533 9.938c-.023.1-.056.197-.098.29L2.82 16.059a1.602 1.602 0 0 0 .313 1.772l4.116 4.24c2.103-3.101 1.796-6.02.836-8.3-.728-1.73-1.832-3.081-2.55-3.831zM9.32 14.01c.615-.183 1.606-.465 2.745-.534-.683-1.725-.848-3.233-.716-4.577.154-1.552.7-2.847 1.235-3.95.113-.235.223-.454.328-.664.149-.297.288-.577.419-.86.217-.47.379-.885.46-1.27.08-.38.08-.72-.014-1.043-.095-.325-.297-.675-.68-1.06a1.6 1.6 0 0 0-1.475.36l-4.95 4.452a1.602 1.602 0 0 0-.513.952l-.427 2.83c.672.59 2.328 2.316 3.335 4.711.09.21.175.43.253.653z"/>`,
  };
  const Ico = ({ n, s = 18 }) => html`<svg class="fi" width=${s} height=${s} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[n]}</svg>`;

  /* ---------- tipos de nó ---------- */
  const TIPOS = {
    inteligencia: { nome: 'Inteligência em texto', sub: 'Texto de contexto' },
    arquivo: { nome: 'Inteligência em arquivo', sub: 'Arquivos e imagens de contexto' },
    biblia: { nome: 'Bíblia da VSL', sub: 'Agente: estuda as VSLs e monta a bíblia' },
    briefing: { nome: 'Briefing de tese', sub: 'Agente: monta a tese com as bíblias ligadas nele' },
    blocos: { nome: 'Blocos de VSL', sub: 'Agente: escreve a VSL bloco por bloco' },
    fonte: { nome: 'Fonte do Blocos de VSL', sub: 'Tese, bíblias ou VSLs de referência' },
    chat: { nome: 'Octopus Chat', sub: 'Conversa usando o que estiver ligado' },
    chatgpt: { nome: 'ChatGPT', sub: 'Motor dos agentes ligados' },
    previa: { nome: 'Arquivo do chat', sub: 'Documento gerado num chat' },
    youtube: { nome: 'YouTube', sub: 'Busca vídeos por termo' },
    nota: { nome: 'Nota', sub: 'Um título e uma anotação no flow' },
    social: { nome: 'Conteúdo das redes sociais', sub: 'Vídeo do YouTube, TikTok ou Instagram' },
    oferta: { nome: 'Oferta', sub: 'De qual projeto é este flow' },
    grupo: { nome: 'Grupo', sub: 'Junta inteligências num contexto só' },
    transcricao: { nome: 'Transcrição', sub: 'Vídeo ou áudio em texto, com o Whisper' },
    doc: { nome: 'Arquivo', sub: 'Cópia de um arquivo do chat, solta no flow' },
    vsl: { nome: 'VSL', sub: 'Transcrição de uma VSL, para a Bíblia da VSL' },
    trarq: { nome: 'Transcrição pronta', sub: 'Texto do vídeo, com o tempo de cada trecho' },
  };
  // quem pode entrar em quem (origem -> destinos aceitos)
  const ACEITA = {
    inteligencia: ['chatgpt', 'inteligencia', 'arquivo'],
    arquivo: ['chatgpt', 'inteligencia', 'arquivo'],
    biblia: ['chatgpt', 'inteligencia', 'arquivo', 'trarq', 'transcricao', 'grupo', 'doc'],
    briefing: ['chatgpt', 'inteligencia', 'arquivo', 'biblia', 'previa', 'trarq', 'transcricao', 'grupo', 'doc'],
    blocos: ['chatgpt'],
    fonte: ['blocos', 'previa', 'doc', 'trarq', 'transcricao', 'arquivo', 'inteligencia', 'grupo'],     // além do Blocos de VSL, aceita arquivos do flow (o briefing que saiu de um chat, uma transcrição…)
    chat: ['chatgpt', 'inteligencia', 'arquivo', 'biblia', 'briefing', 'blocos', 'fonte', 'previa', 'trarq', 'transcricao', 'grupo', 'oferta', 'youtube', 'doc', 'vsl', 'social'],
    social: [],
    nota: [],
    doc: ['chatgpt'],          // o ChatGPT pode vir antes dos arquivos (ex.: ChatGPT → bíblias → Briefing de tese → Chat)
    vsl: [],
    oferta: [],
    youtube: ['blocos'],
    transcricao: [],
    grupo: [],
    chatgpt: ['oferta'],      // a Oferta ligada no ChatGPT vale para tudo o que vem depois dele
  };
  const SAI = { inteligencia: true, arquivo: true, chatgpt: true, biblia: true, briefing: true, blocos: true, chat: false, transcricao: false, grupo: true, oferta: true, youtube: true, social: true, doc: true, fonte: true, vsl: true };

  const LONGO = 500;       // a partir daqui, texto enviado no chat vira arquivo
  let ctx = null;          // callbacks vindos da página
  let forcar = null;       // re-render externo
  let api = null;          // funções expostas a partir do componente

  function MenuNo({ id, itens }) {
    const [aberto, setAberto] = useState(false);
    const rf = useReactFlow();
    useEffect(() => {
      if (!aberto) return;
      const fechar = (e) => { if (!e.target.closest || !e.target.closest('.an-menu')) setAberto(false); };
      document.addEventListener('pointerdown', fechar);
      return () => document.removeEventListener('pointerdown', fechar);
    }, [aberto]);
    return html`<div class="an-menu nodrag">
      <button class="an-mini" onClick=${() => setAberto(!aberto)} aria-label="Opções do nó" aria-expanded=${aberto} title="Opções"><${Ico} n="pontos" s=${16} /></button>
      ${aberto ? html`<div class="an-pop" role="menu">
        ${(itens || []).map((it) => html`<button key=${it.rot} role="menuitem" onClick=${() => { setAberto(false); it.fn(); }}><${Ico} n=${it.ico} s=${14} />${it.rot}</button>`)}
        <button role="menuitem" onClick=${() => { setAberto(false); ctx.copiarLink(id); }}><${Ico} n="abrir" s=${14} />Copiar link</button>
        <button role="menuitem" onClick=${() => { setAberto(false); rf.deleteElements({ nodes: [{ id }] }); }}><${Ico} n="lixo" s=${14} />Excluir nó</button>
      </div>` : null}
    </div>`;
  }

  /* campo de mensagem: o que começa com #, / ou @ (função, skill, persona) aparece em verde. O texto real fica transparente por cima deste espelho */
  function pintarMarcas(texto, personas) {
    const esc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const nomes = (personas || []).map((p) => p.nome).filter(Boolean).sort((a, b) => b.length - a.length).map(esc);
    const re = new RegExp('(^|\\s)(' + (nomes.length ? '@(?:' + nomes.join('|') + ')|' : '') + '[#/@][^\\s#@/]*)', 'gi');
    const out = []; let fim = 0, m;
    while ((m = re.exec(texto))) {
      const ini = m.index + m[1].length;
      if (ini > fim) out.push(texto.slice(fim, ini));
      out.push(html`<span class="marca" key=${ini}>${m[2]}</span>`);
      fim = ini + m[2].length;
      if (!m[0].length) re.lastIndex++;
    }
    out.push(texto.slice(fim) + '\u200b');
    return out;
  }

  function Cabeca({ tipo, titulo, sub, extra, id, itens }) {
    return html`<div class="an-head">
      <span class="an-ico">${html`<${Ico} n=${tipo} s=${tipo === 'chatgpt' ? 17 : 18} />`}</span>
      <div class="an-t"><b>${titulo}</b>${sub ? html`<small>${sub}</small>` : null}</div>${extra || null}${id ? html`<${MenuNo} id=${id} itens=${itens} />` : null}</div>`;
  }

  /* ligação com X para desligar, que aparece ao passar o mouse */
  function Ligacao({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, selected }) {
    const [sobre, setSobre] = useState(false);
    const t = useRef(null);
    const rf = useReactFlow();
    const [path, lx, ly] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
    const entrar = () => { clearTimeout(t.current); setSobre(true); };
    const sair = () => { t.current = setTimeout(() => setSobre(false), 250); };
    return html`<g onMouseEnter=${entrar} onMouseLeave=${sair} class=${sobre ? 'aedge-on' : ''}>
      <${BaseEdge} id=${id} path=${path} interactionWidth=${24} />
      <${EdgeLabelRenderer}>
        <button class=${'aedge-x nodrag nopan ' + (sobre || selected ? 'on' : '')} style=${{ transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }}
          onMouseEnter=${entrar} onMouseLeave=${sair} onClick=${() => rf.deleteElements({ edges: [{ id }] })} aria-label="Desligar" title="Desligar">
          <${Ico} n="x" s=${12} /></button>
      <//>
    </g>`;
  }
  /* ligação do chat com os cartões de etapa: acompanha o cartão quando ele é arrastado; não dá para desligar */
  function LigacaoFixa({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition }) {
    const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
    return html`<${BaseEdge} id=${id} path=${path} />`;
  }
  const edgeTypes = { atlas: Ligacao, fixa: LigacaoFixa };
  const Canto = ({ minW, minH }) => html`<${NodeResizeControl} position="bottom-right" minWidth=${minW} minHeight=${minH} className="an-resize" style=${{ background: 'transparent', border: 'none' }}>
    <span class="an-canto" title="Arraste para mudar o tamanho"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      ${[[12, 2], [8, 6], [12, 6], [4, 10], [8, 10], [12, 10]].map(([x, y]) => html`<circle key=${x + '-' + y} cx=${x} cy=${y} r="1.35" fill="currentColor" />`)}</svg></span><//>`;

  function NoAgente({ id, data, type, selected }) {
    const info = ctx.info(id, type);
    return html`<div class=${'an ' + (selected ? 'an-on ' : '') + (info.rodando ? 'rodando' : '')}>
      ${ACEITA[type].length ? html`<${Handle} type="target" position=${Position.Left} />` : null}
      <${Cabeca} id=${id} tipo=${type} titulo=${TIPOS[type].nome} sub=${TIPOS[type].sub} />
      <div class="an-body">
        <div class="an-status"><span class=${'dot ' + (info.estado || '')}></span>${info.status}</div>
        ${info.ligados && info.ligados.length ? html`<div class="an-lig">${info.ligados.map((l) => html`<span key=${l}>${l}</span>`)}</div>` : null}
      </div>
      ${SAI[type] ? html`<${Handle} type="source" position=${Position.Right} />` : null}
    </div>`;
  }

  function CampoBiblia({ id, k, slot, biblias, mudar }) {
    const ref = useRef(null);
    const [enviando, setEnviando] = useState(false);
    const [erro, setErro] = useState('');
    const subir = async (e) => {
      const f = (e.target.files || [])[0]; e.target.value = ''; if (!f) return;
      setErro(''); setEnviando(true);
      try { const r = await ctx.enviarArquivo(id, f); mudar({ origem: 'arquivo', nome: r.nome, caracteres: r.caracteres }); }
      catch (err) { setErro(err.message); }
      setEnviando(false);
    };
    if (slot) return html`<div class="an-slot cheio">
      <span class="an-slot-n">${k + 1}</span><${Ico} n=${slot.origem === 'cofre' ? 'cofre' : 'arquivo'} s=${14} />
      <span class="an-slot-t" title=${slot.nome}>${slot.nome}</span>
      <button class="nodrag" onClick=${() => { if (slot.origem === 'arquivo') ctx.removerArquivo(id, slot.nome); mudar(null); }} aria-label="Tirar bíblia"><${Ico} n="x" s=${12} /></button></div>`;
    return html`<div class="an-slot">
      <span class="an-slot-n">${k + 1}</span>
      <button class="an-slot-b nodrag" onClick=${() => ref.current && ref.current.click()} disabled=${enviando}><${Ico} n="upload" s=${13} />${enviando ? 'Enviando…' : 'Subir'}</button>
      <select class="an-slot-s nodrag" value="" onChange=${(e) => { const b = biblias.find((x) => x.caminho === e.target.value); if (b) mudar({ origem: 'cofre', caminho: b.caminho, nome: b.rotulo }); }}>
        <option value="">Do cofre…</option>
        ${biblias.map((b) => html`<option key=${b.caminho} value=${b.caminho}>${b.rotulo}</option>`)}
      </select>
      <input ref=${ref} type="file" hidden accept=".md,.txt" onChange=${subir} />
      ${erro ? html`<div class="an-erro">${erro}</div>` : null}</div>`;
  }

  function NoBriefing({ id, data, type, selected }) {
    const info = ctx.info(id, type);
    const biblias = ctx.biblias();
    const slots = [0, 1, 2].map((i) => (data.slots || [])[i] || null);
    const mudar = (i, v) => { const n = [...slots]; n[i] = v; api && api.patch(id, { slots: n }); };
    const qtd = slots.filter(Boolean).length;
    return html`<div class=${'an an-brief ' + (selected ? 'an-on ' : '') + (info.rodando ? 'rodando' : '')}>
      <${Handle} type="target" position=${Position.Left} />
      <${Cabeca} id=${id} tipo="briefing" titulo="Briefing de tese" sub=${qtd ? qtd + (qtd > 1 ? ' bíblias carregadas' : ' bíblia carregada') : 'Suba de 1 a 3 bíblias de VSL'} />
      <div class="an-body">
        <div class="an-slots">${slots.map((sl, i) => html`<${CampoBiblia} key=${i} id=${id} k=${i} slot=${sl} biblias=${biblias} mudar=${(v) => mudar(i, v)} />`)}</div>
        <div class="an-status"><span class=${'dot ' + (info.estado || '')}></span>${info.status}</div>
        ${info.ligados && info.ligados.length ? html`<div class="an-lig">${info.ligados.map((l) => html`<span key=${l}>${l}</span>`)}</div>` : null}
      </div>
      <${Handle} type="source" position=${Position.Right} />
    </div>`;
  }

  /* ---- nó de chat: a conversa acontece dentro do nó ---- */
  /* o guia do chat de Criativos (o "i" ao lado do Contexto): tudo o que dá para pedir neste chat, por tipo */
  const GUIA_CRIATIVOS = [
    ['Criar anúncios', [
      ['Ultra-modelagem', '/ultra-modelagem', 'A partir de um conteúdo viral, de um anúncio de concorrente ou de um anúncio seu, lista as ideias. Você escolhe uma e ela busca a narrativa e o formato para construir o anúncio.'],
      ['Partir de uma ideia', 'Passe a ideia: "quero um anúncio com esta ideia: …"', 'Você traz a big idea e ele busca a narrativa e o formato que combinam com ela. Também pode pedir a lista: "liste ideias com base nos meus anúncios" ou "com base nos anúncios do controle de mercado".'],
      ['Partir de um anúncio', 'Cole o anúncio: "construa com base neste anúncio"', 'Ele tira a ideia do anúncio que você colou e escreve a sua versão, com narrativa e formato.'],
      ['Partir de um formato', '"Quero um anúncio neste formato: …"', 'Você escolhe o formato e ele busca a narrativa e a ideia que combinam com ele.'],
      ['Partir de uma narrativa', '"Quero um anúncio com esta narrativa: …"', 'Você escolhe a narrativa e ele busca o formato e a ideia que combinam com ela.'],
    ]],
    ['Salvar no Cérebro', [
      ['Subir os anúncios', '"Suba esses anúncios no Cérebro"', 'Ele diz quantos anúncios foram feitos neste chat e em qual remessa entram, e pede a sua confirmação. A numeração continua de onde a oferta parou (parou no 10: entram 11, 12, 13…).'],
      ['Remessa', 'Perguntada no primeiro anúncio do chat', 'Você escolhe entre continuar na última remessa ou abrir uma nova. Vale para todos os anúncios deste chat.'],
    ]],
    ['Atualizar o que já existe', [
      ['Números do anúncio', '"O AD 12 teve hook rate 38% e hold rate 21%"', 'Grava nas propriedades do anúncio. Tráfego: gasto, faturamento, hook rate, hold rate, IC, CTR, CPA, CPM e conversão do checkout. VSL: play rate, retenção do 1º minuto, retenção ao pitch e conversão.'],
      ['Fase do anúncio', '"O AD 12 já está no ar" · "o AD 09 validou"', 'Muda o status: para gravação, gravado, para edição, editado, no ar, validou, não validou.'],
      ['Melhorar um hook', '"Melhore o hook do AD 12"', 'Reescreve o hook olhando os que já validaram e os dos concorrentes.'],
    ]],
    ['Consultar', [
      ['Meus hooks', '"Quais hooks mais validaram?"', 'Lê os anúncios salvos da oferta e os números de cada um.'],
      ['Concorrentes', '"Quais são os hooks dos meus concorrentes?"', 'Lê o controle de mercado da oferta.'],
      ['O que a oferta tem', '"Liste os anúncios da remessa 2"', 'Lista anúncios, remessas, big ideias e personas da oferta.'],
    ]],
  ];

  function NoChat({ id, data, selected }) {
    const info = ctx.chat(id);
    const [texto, setTexto] = useState('');
    const lista = useRef(null), caixa = useRef(null);
    const memoria = data.memoria !== false;
    // a caixa de digitação cresce com o texto (até umas oito linhas; depois rola)
    useEffect(() => { const el = caixa.current; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px'; } }, [texto]);
    useEffect(() => { const el = lista.current; if (el) el.scrollTop = el.scrollHeight; }, [info.msgs.length, info.ultimo]);
    // texto com mais de LONGO caracteres vira arquivo anexado (colado ou na hora de enviar), como no ChatGPT
    const [anexos, setAnexos] = useState([]);
    // três pontinhos de um arquivo já enviado no chat: renomear ou excluir de vez
    const [anxMenu, setAnxMenu] = useState(null);
    const [anxRen, setAnxRen] = useState(null);
    const espelho = useRef(null);
    const [galMenu, setGalMenu] = useState(null);
    const [galRen, setGalRen] = useState(null);
    const nArq = info.msgs.reduce((n, m) => n + (m.anexos || []).length + (m.doc && !m.stream ? 1 : 0), 0) + (info.vslArq ? 1 : 0);
    const nArqAntes = useRef(null);
    useEffect(() => { if (nArqAntes.current != null && nArq > nArqAntes.current && data.galFechada) api && api.patch(id, { galFechada: false }); nArqAntes.current = nArq; }, [nArq]);
    const nomeNovo = (extra = 0) => 'Texto colado ' + (info.msgs.reduce((n, m) => n + ((m.anexos || []).length), 0) + anexos.length + extra + 1);
    const colar = (e) => { const t = (e.clipboardData && e.clipboardData.getData('text')) || ''; if (t.trim().length > LONGO) { e.preventDefault(); setAnexos((a) => [...a, { nome: nomeNovo(), texto: t.trim() }]); } };
    // @ chama uma persona da oferta ligada a este chat (nó Oferta): a nota dela vai junto na mensagem
    const personas = ctx.personas ? ctx.personas(id) : null;
    const arroba = (texto.match(/(?:^|\s)@([^\s@]*)$/) || [])[1];
    const sem = (x) => x.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const sug = arroba != null && personas ? personas.filter((x) => sem(x.nome).includes(sem(arroba))).slice(0, 6) : [];
    const chamar = (nome) => setTexto(texto.replace(/@([^\s@]*)$/, '@' + nome + ' '));
    // # abre os comandos: as funções do agente ligado neste chat; "ver todas" mostra as dos outros agentes
    const [cmdTodos, setCmdTodos] = useState(false);
    // microfone: fala em vez de digitar (o Whisper transcreve no computador e o texto entra no campo)
    const [mic, setMic] = useState('');
    const ditar = () => window.AtlasDitado && window.AtlasDitado.alternar({ estado: setMic, texto: (t) => setTexto((a) => (a.trim() ? a.trim() + ' ' : '') + t) });
    let cerquilha = (texto.match(/(?:^|\s)#([^#]*)$/) || [])[1];
    // função já escolhida ("#salvar-vsl " e o resto da mensagem): a lista fecha e a pessoa segue escrevendo
    if (cerquilha != null && /^[\w-]+\s/.test(cerquilha) && ctx.comandos && ctx.comandos(id).some((c) => c.funcao && c.nome === cerquilha.split(/\s/)[0])) cerquilha = null;
    const cmds = cerquilha != null && ctx.comandos ? ctx.comandos(id) : [];
    // "/" invoca uma skill: ela entra no texto como /nome e vale só para aquele pedido
    const barra = (texto.match(/(?:^|\s)\/([\w-]*)$/) || [])[1];
    const skl = barra != null && ctx.skills ? ctx.skills(id) : [];
    const sklSug = skl.filter((s) => sem(s.id + ' ' + s.nome).includes(sem(barra || '').trim())).sort((a, b) => (b.meu ? 1 : 0) - (a.meu ? 1 : 0));
    const usarSkill = (s) => setTexto(texto.replace(/(^|\s)\/[\w-]*$/, '$1/' + s.id + ' '));
    const temMeus = cmds.some((c) => c.meu);
    const cmdSug = cmds.filter((c) => (cmdTodos || !temMeus || c.meu) && sem(c.nome + ' ' + c.agenteNome).includes(sem(cerquilha || '').trim()));
    const usarCmd = (c) => { const resto = texto.replace(/(^|\s)#[^#]*$/, '$1'); setCmdTodos(false);
      if (c.acao) { setTexto(resto); ctx.comando(id, c.id); }
      else if (c.envia) { setTexto(''); ctx.enviarChat(id, (resto + c.texto).trim()); }
      else setTexto(resto + c.texto); };
    const enviar = () => {
      if (info.rodando) return;
      let t = texto.trim(), ax = anexos;
      if (t.length > LONGO) { ax = [...ax, { nome: nomeNovo(), texto: t }]; t = ''; }
      if (!t && !ax.length) return;
      if (info.semOferta) { ctx.enviarChat(id, t, ax); return; }      // sem nó Oferta: só avisa e mantém o que foi digitado
      setTexto(''); setAnexos([]); ctx.enviarChat(id, t, ax);
    };
    const igual = (ref) => data.previa != null && String(data.previa) === String(ref);
    const alternar = (ref) => { if (igual(ref) && ctx.previaLigada(id)) { ctx.aviso('Este arquivo está ligado a outro nó. Tire a ligação para fechar.'); return; } api && api.patch(id, { previa: igual(ref) ? null : ref }); };
    // arquivo novo NÃO abre sozinho: ele aparece na lista de arquivos do chat e a pessoa abre se quiser (clicando nele)
    return html`<div class=${'an an-chat ' + (selected ? 'an-on ' : '') + (info.rodando ? 'rodando' : '')}>
      <${Handle} type="source" id="et" position=${Position.Right} isConnectable=${false} className="h-fixa" style=${{ top: 26 }} />
      <${NodeResizeControl} position="bottom-right" minWidth=${320} minHeight=${360} className="an-resize" style=${{ background: 'transparent', border: 'none' }}>
        <span class="an-canto" title="Arraste para mudar o tamanho"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          ${[[12, 2], [8, 6], [12, 6], [4, 10], [8, 10], [12, 10]].map(([x, y]) => html`<circle key=${x + '-' + y} cx=${x} cy=${y} r="1.35" fill="currentColor" />`)}
        </svg></span>
      <//>
      <${Handle} type="target" position=${Position.Left} />
      <${Cabeca} id=${id} tipo="chat" titulo="Octopus Chat" sub=""
        extra=${html`<div class="an-acoes">
          <button class=${'an-mem nodrag ' + (memoria ? 'on' : '')} onClick=${() => api && api.patch(id, { memoria: !memoria })}
            title=${memoria ? 'Janela de contexto ligada: o chat lembra das mensagens anteriores' : 'Janela de contexto desligada: cada mensagem é respondida sozinha'} aria-pressed=${memoria}>
            <${Ico} n="memoria" s=${13} />${memoria ? 'Contexto' : 'Sem contexto'}</button>
          ${info.area === 'criativos' ? html`<button class=${'an-mini nodrag' + (data.guia ? ' on' : '')} onClick=${() => api && api.patch(id, { guia: !data.guia })} aria-pressed=${!!data.guia}
            title="O que dá para fazer neste chat" aria-label="O que dá para fazer neste chat"><${Ico} n="guia" s=${16} /></button>` : null}
          ${nArq ? html`<button class=${'an-mini nodrag' + (data.galFechada ? '' : ' on')} onClick=${() => api && api.patch(id, { galFechada: !data.galFechada })} aria-pressed=${!data.galFechada}
            title=${data.galFechada ? 'Mostrar os arquivos deste chat' : 'Esconder os arquivos deste chat'} aria-label="Arquivos deste chat"><${Ico} n="pasta" s=${15} /></button>` : null}
          ${info.msgs.length ? html`<button class="an-mini nodrag" onClick=${() => ctx.limparChat(id)} title="Apagar a conversa" aria-label="Apagar a conversa"><${Ico} n="limpar" s=${14} /></button>` : null}
        </div>`} />
      <div class="an-msgs nodrag nowheel" ref=${lista}>
        ${info.msgs.length ? info.msgs.map((m, i) => m.r === 'user'
          ? html`<div class="cm u" key=${i}>${(m.anexos || []).map((a, k) => { const ref = i + ':' + k;
              return html`<div key=${k} class="cm-anx-l nodrag">
              ${anxRen === ref ? html`<input class="anx-ren nodrag" autoFocus defaultValue=${a.nome} maxLength="80" aria-label="Novo nome do arquivo"
                  onKeyDown=${(e) => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); const v = e.target.value; setAnxRen(null); ctx.renomearAnexo(id, i, k, v); } else if (e.key === 'Escape') setAnxRen(null); }}
                  onBlur=${(e) => { const v = e.target.value; setAnxRen(null); ctx.renomearAnexo(id, i, k, v); }} />`
                : html`<button class=${'cm-anx nodrag' + (igual(ref) ? ' on' : '')} onClick=${() => alternar(ref)} title=${igual(ref) ? 'Fechar a visualização' : 'Abrir o texto ao lado'}>
              <span class="gal-i"><${Ico} n="arquivo" s=${13} /></span><span class="cm-anx-t"><b>${a.nome}</b><small>${a.texto.length.toLocaleString('pt-BR')} caracteres</small></span></button>`}
              <button class="anx-mais nodrag" onClick=${() => setAnxMenu(anxMenu === ref ? null : ref)} title="Renomear ou excluir" aria-label=${'Opções de ' + a.nome} aria-expanded=${anxMenu === ref}>⋯</button>
              ${anxMenu === ref ? html`<div class="anx-pop nodrag" role="menu" onMouseLeave=${() => setAnxMenu(null)}>
                <button role="menuitem" onClick=${() => { setAnxMenu(null); setAnxRen(ref); }}><${Ico} n="lapis" s=${13} />Renomear</button>
                <button role="menuitem" class="per" onClick=${() => { setAnxMenu(null); ctx.excluirAnexo(id, i, k); }}><${Ico} n="lixo" s=${13} />Excluir</button></div>` : null}</div>`; })}${m.t ? html`<div>${m.t}</div>` : null}</div>`
          : html`<div class="cm b" key=${i}>
              ${m.t ? html`<div class="md" dangerouslySetInnerHTML=${{ __html: ctx.md(m.t) }}></div>` : null}
              ${m.doc ? html`<button class=${'cm-arq nodrag' + (data.previa === i ? ' on' : '')} onClick=${() => alternar(i)}
                  title=${data.previa === i ? 'Fechar a visualização' : 'Abrir a visualização do arquivo'}>
                  <span class="cm-arq-top"><span class="cm-arq-i"><${Ico} n="arquivo" s=${17} /></span><span class="cm-arq-a"><${Ico} n=${data.previa === i ? 'x' : 'olho'} s=${14} /></span></span>
                  <span class="cm-arq-t"><b>${ctx.docNome(m)}</b><small>${m.doc.length.toLocaleString('pt-BR')} caracteres</small>
                    <em>${m.inserido ? (m.inserido.resumo || 'Salvo no Cérebro') : data.previa === i ? 'Aberto embaixo' : 'Clique para ver'}</em></span></button>` : null}
              ${m.inserido && m.inserido.avisos ? html`<div class="perm-cx nodrag"><span>${m.inserido.avisos.join(' ')}</span></div>` : null}
              ${m.stream ? html`<div class="cm-st">${m.status || (m.t ? 'Escrevendo…' : 'Pensando…')}</div>` : null}
              ${m.permissao ? html`<div class="perm-cx nodrag"><span>O macOS bloqueou a pasta <b>${m.permissao.nome}</b>.${m.permissao.negado ? ' Nos Ajustes do Sistema, ligue a pasta para o Octopus IA e clique de novo.' : ''}</span>
                <button class="cm-btn forte" disabled=${!!m.permissao.rodando} onClick=${() => ctx.permitir(id, i)}>${m.permissao.rodando ? 'Aguardando o macOS…' : 'Permitir acesso'}</button></div>` : null}
              ${m.erro ? html`<div class="an-erro">${m.erro}</div>` : null}
              ${m.escolhaRemessa ? html`<div class="perm-cx nodrag"><span>Em qual remessa entram os anúncios deste chat?</span>
                <span class="perm-bts"><button class="cm-btn" onClick=${() => ctx.escolherRemessa(id, i, 'ultima')}>Continuar na Remessa ${String(m.escolhaRemessa.ultima).padStart(2, '0')}</button>
                <button class="cm-btn forte" onClick=${() => ctx.escolherRemessa(id, i, 'nova')}>Abrir a Remessa ${String(m.escolhaRemessa.ultima + 1).padStart(2, '0')}</button></span></div>` : null}
              ${m.confirmar && !m.stream && i === info.msgs.length - 1 ? html`<div class="perm-cx nodrag"><span>${m.confirmar}</span>
                <span class="perm-bts"><button class="cm-btn" onClick=${() => ctx.permitirSalvar(id, i, false)}>Agora não</button>
                <button class="cm-btn forte" onClick=${() => ctx.permitirSalvar(id, i, true)}>Permitir salvar</button></span></div>` : null}</div>`)
        : html`<div class="cm-vazio">${!info.gpt ? null
            : info.agentes.length ? html`<b>${info.agentes[0]}</b><span>${info.pede}</span>
                <div class="cm-sug">${info.quebra.map((q) => html`<button key=${q} class="nodrag" onClick=${() => (/[: ]$/.test(q) ? setTexto(q) : ctx.enviarChat(id, q))}>${q.replace(/[: ]+$/, '…')}</button>`)}</div>`
            : 'Pergunte qualquer coisa. Ligue uma Bíblia da VSL ou um Briefing de tese antes deste chat (um por chat) e ele passa a fazer só essa tarefa.'}</div>`}
      </div>
      ${(() => { const refs = []; let v = 0; const nDocs = info.msgs.filter((m) => m.doc && !m.stream).length;
        if (info.vslArq) refs.push({ ref: info.vslArq.ref, nome: info.vslArq.nome, fixo: true });      // chat da Bíblia: a VSL enviada vem primeiro; a bíblia que sai dela vem depois
        info.msgs.forEach((m, i) => { (m.anexos || []).forEach((a, k) => refs.push({ ref: i + ':' + k, nome: a.nome })); if (m.doc && !m.stream) { v++; refs.push({ ref: i, nome: ctx.docNome(m), v: nDocs > 1 ? v : 0 }); } });
        return refs.length && !data.galFechada ? html`<div class="an-galeria nodrag nowheel"><span class="gal-tit"><${Ico} n="arquivo" s=${12} />Arquivos · ${refs.length}
            <button class="gal-x" onClick=${() => api && api.patch(id, { galFechada: true })} title="Fechar os arquivos (reabra pela pasta, lá em cima)" aria-label="Fechar os arquivos"><${Ico} n="x" s=${13} /></button></span>
          <div class=${'gal-lista' + (galMenu != null ? ' com-menu' : '')}>${refs.map((r) => html`<span key=${r.ref} class="gal-item">${galRen === r.ref
            ? html`<input class="anx-ren nodrag" autoFocus defaultValue=${r.nome} maxLength="80" aria-label="Novo nome do arquivo"
                onKeyDown=${(e) => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); const v = e.target.value; setGalRen(null); ctx.renomearArquivo(id, r.ref, v); } else if (e.key === 'Escape') setGalRen(null); }}
                onBlur=${(e) => { const v = e.target.value; setGalRen(null); ctx.renomearArquivo(id, r.ref, v); }} />`
            : html`<button class=${'gal-arq' + (igual(r.ref) ? ' on' : '')} draggable="true"
            onDragStart=${(e) => { e.stopPropagation(); e.dataTransfer.setData('application/atlas-doc', JSON.stringify({ chat: id, ref: r.ref })); e.dataTransfer.effectAllowed = 'copy'; }}
            onClick=${() => alternar(r.ref)} title=${r.nome + (r.v ? ' · versão ' + r.v : '') + ' · clique para abrir, arraste para fora para soltar uma cópia no flow'}>
            <span class="gal-i"><${Ico} n="arquivo" s=${13} /></span><span class="gal-t">${r.nome}${r.v ? html`<small> v${r.v}</small>` : null}</span></button>`}
            ${r.fixo ? null : html`<button class="anx-mais nodrag" onClick=${() => setGalMenu(galMenu === r.ref ? null : r.ref)} title="Renomear ou excluir" aria-label=${'Opções de ' + r.nome} aria-expanded=${galMenu === r.ref}>⋯</button>`}
            ${galMenu === r.ref ? html`<div class="anx-pop nodrag" role="menu" onMouseLeave=${() => setGalMenu(null)}>
              <button role="menuitem" onClick=${() => { setGalMenu(null); setGalRen(r.ref); }}><${Ico} n="lapis" s=${13} />Renomear</button>
              <button role="menuitem" class="per" onClick=${() => { setGalMenu(null); ctx.excluirArquivo(id, r.ref); }}><${Ico} n="lixo" s=${13} />Excluir</button></div>` : null}</span>`)}</div></div>` : null; })()}
      ${data.guia && info.area === 'criativos' ? html`<div class="an-guia nodrag nowheel">
        <div class="gu-h"><b>O que dá para fazer neste chat</b><button class="an-mini" onClick=${() => api && api.patch(id, { guia: false })} title="Fechar" aria-label="Fechar o guia"><${Ico} n="x" s=${14} /></button></div>
        <div class="gu-c">${GUIA_CRIATIVOS.map(([tit, linhas]) => html`<section key=${tit}><h4>${tit}</h4>
          <table><thead><tr><th>Função</th><th>Como chamar</th><th>O que faz</th></tr></thead>
            <tbody>${linhas.map((l) => html`<tr key=${l[0]}><td><b>${l[0]}</b></td><td class="gu-ch">${l[1]}</td><td>${l[2]}</td></tr>`)}</tbody></table></section>`)}
          <p class="gu-pe">Este chat sempre trabalha dentro de uma oferta: o nó Oferta é obrigatório. Ele só grava quando você pede.</p></div>
      </div>` : null}
      ${info.semOferta && info.msgs.length ? html`<div class="an-prox nodrag" style=${{ color: 'var(--warn, #f5b942)', fontSize: '12.5px', padding: '8px 12px' }}>Falta o nó Oferta. Ligue um nó Oferta a este chat para continuar.</div>` : null}
      ${info.proxima && info.msgs.length && !info.rodando ? html`<div class="an-prox nodrag"><button class="cm-btn forte" onClick=${() => ctx.enviarChat(id, info.proxima)}>${info.proxima}</button></div>` : null}
      <div class=${'an-input nodrag' + (anexos.length ? ' com-anexo' : '')}>
        ${anexos.length ? html`<div class="an-anexos">${anexos.map((a, k) => html`<span key=${k} class="anx-chip"><span class="gal-i"><${Ico} n="arquivo" s=${12} /></span>
          <span class="cm-anx-t"><b>${a.nome}</b><small>${a.texto.length.toLocaleString('pt-BR')} caracteres</small></span>
          <button onClick=${() => setAnexos((l) => l.filter((_, x) => x !== k))} aria-label="Tirar o anexo"><${Ico} n="x" s=${12} /></button></span>`)}</div>` : null}
        ${cerquilha != null && cmds.length ? html`<div class="an-arroba nowheel">
          <span class="cmd-topo"><span>${cmdTodos || !temMeus ? 'Todas as funções' : 'Funções de ' + (cmds.find((c) => c.meu) || {}).agenteNome}</span>
            ${temMeus ? html`<u role="button" onMouseDown=${(e) => { e.preventDefault(); setCmdTodos(!cmdTodos); }}>${cmdTodos ? 'Voltar' : 'Ver todas'}</u>` : null}</span>
          ${cmdSug.length ? cmdSug.map((c) => html`<button key=${c.id} onMouseDown=${(e) => { e.preventDefault(); usarCmd(c); }}><b>#${c.nome}</b><small>${(cmdTodos || !temMeus ? c.agenteNome + (c.desc ? ' · ' : '') : '') + c.desc}</small></button>`) : html`<span class="cmd-topo">Nenhuma função com esse nome</span>`}</div>` : null}
        ${barra != null && skl.length ? html`<div class="an-arroba nowheel"><span class="cmd-topo"><span>Skills</span></span>
          ${sklSug.length ? sklSug.map((s) => html`<button key=${s.id} onMouseDown=${(e) => { e.preventDefault(); usarSkill(s); }}><b>/${s.id}</b><small>${s.resumo || s.nome}</small></button>`) : html`<span class="cmd-topo">Nenhuma skill com esse nome</span>`}</div>` : null}
        ${sug.length ? html`<div class="an-arroba nowheel">${sug.map((x) => html`<button key=${x.nome} onMouseDown=${(e) => { e.preventDefault(); chamar(x.nome); }}><b>@${x.nome}</b><small>${x.resumo}</small></button>`)}</div>` : arroba != null && !personas ? html`<div class="an-arroba nowheel"><span class="cmd-topo"><span>As personas são de uma oferta: ligue um nó Oferta a este chat para chamar uma com @.</span></span></div>`
          : arroba != null && personas && !personas.length ? html`<div class="an-arroba nowheel"><span class="cmd-topo"><span>Esta oferta ainda não tem personas. Crie em Criativos › Personas.</span></span></div>` : null}
        <div class="an-input-l"><div class="an-ta"><div class="an-ta-esp" ref=${espelho} aria-hidden="true">${pintarMarcas(texto, personas)}</div><textarea ref=${caixa} rows="1" class="nowheel" onScroll=${(e) => { if (espelho.current) espelho.current.scrollTop = e.target.scrollTop; }} placeholder=${anexos.length ? 'Escreva o que fazer com o texto…' : personas && personas.length ? 'Mensagem… (# funções, / skills, @ persona)' : 'Mensagem… (# funções, / skills)'} value=${texto} onChange=${(e) => setTexto(e.target.value)} onPaste=${colar}
          onKeyDown=${(e) => { if (barra != null && sklSug.length && (e.key === 'Enter' || e.key === 'Tab')) { e.preventDefault(); usarSkill(sklSug[0]); return; } if (barra != null && e.key === 'Escape') { setTexto(texto.replace(/(^|\s)\/[\w-]*$/, '$1')); return; } if (cerquilha != null && cmdSug.length && (e.key === 'Enter' || e.key === 'Tab')) { e.preventDefault(); usarCmd(cmdSug[0]); return; } if (cerquilha != null && e.key === 'Escape') { setTexto(texto.replace(/(^|\s)#[^#]*$/, '$1')); return; } if (sug.length && (e.key === 'Enter' || e.key === 'Tab')) { e.preventDefault(); chamar(sug[0].nome); return; } if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); } }}></textarea></div>
        <button class=${'an-mic ' + mic} onClick=${ditar} disabled=${mic === 'transcrevendo'} title=${mic === 'gravando' ? 'Parar e transcrever' : mic === 'transcrevendo' ? 'Transcrevendo…' : 'Falar em vez de digitar'} aria-label="Microfone"><${Ico} n="mic" s=${15} /></button>
        ${info.rodando
          ? html`<button class="parar" onClick=${() => ctx.pararChat(id)} title="Parar a resposta" aria-label="Parar a resposta"><${Ico} n="parar" s=${15} /></button>`
          : html`<button onClick=${enviar} disabled=${!texto.trim() && !anexos.length} aria-label="Enviar"><${Ico} n="enviar" s=${15} /></button>`}</div>
      </div>
    </div>`;
  }

  /* visualização do arquivo gerado no chat: painel grande ao lado do chat, ligado a ele por uma linha */
  function NoPrevia({ data }) {
    const info = ctx.chat(data.chat), a = ctx.arquivo(data.chat, data.i), m = a && a.m;
    if (!a) return null;
    const fechar = () => { if (data.ligada) { ctx.aviso('Este arquivo está ligado a outro nó. Tire a ligação para fechar.'); return; } api && api.patch(data.chat, { previa: null }); };
    return html`<div class="an an-previa baixo" style=${{ height: data.h + 'px' }}>
      <div class="an-head"><span class="an-ico"><${Ico} n="arquivo" s=${18} /></span>
        <div class="an-t"><b>${a.nome}</b><small>${a.texto.length.toLocaleString('pt-BR')} caracteres${a.vsl ? ' · a VSL deste chat' : a.anexo ? ' · enviado no chat' : ''}</small></div>
        <button class="an-mini nodrag" onClick=${fechar} title=${data.ligada ? 'Ligado a outro nó: tire a ligação para fechar' : 'Fechar'} aria-label="Fechar a visualização"><${Ico} n="x" s=${15} /></button></div>
      ${a.anexo && !/^### /m.test(a.texto) ? html`<div class="pv-corpo pv-texto nodrag nowheel">${a.texto}</div>` : html`<div class="pv-corpo md nodrag nowheel" dangerouslySetInnerHTML=${{ __html: ctx.md(a.texto) }}></div>`}
      <div class="pv-pe nodrag">${a.anexo ? null : m.inserido
        ? html`<span class="cm-ok"><${Ico} n="cofre" s=${13} />${m.inserido.resumo ? m.inserido.resumo + ' · ' : 'Inserido em '}${m.inserido.caminho}</span><a class="cm-btn" href=${m.inserido.obsidian}>Abrir a nota</a>`
        : null}
        <button class="cm-btn" onClick=${() => ctx.copiar(a.texto)}>Copiar</button></div>
      <${Handle} type="source" position=${Position.Right} style=${{ top: 26 }} title="Ligue no Briefing de tese (ou num chat) para usar este arquivo" />
    </div>`;
  }

  /* Etapas do chat: cada "✓ Etapa N · nome: escolha" que o agente registra vira um cartãozinho à direita do chat, ligado a ele.
     Quando sai o arquivo final, os cartões se juntam num só (dá para ver separado de novo). Não são salvos: saem das mensagens */
  function etapasDoChat(msgs) {
    const mapa = new Map();
    (msgs || []).forEach((m) => { if (m.r !== 'bot' || !m.t) return;
      for (const l of String(m.t).split('\n')) {
        const x = l.replace(/[*_`>]/g, '').trim().match(/^(?:[-•]\s*)?[✓✔☑✅]\s*Etapa\s*(\d+)\s*[·:\-–—]\s*([^:]{2,60}):\s*(.+)$/i);
        if (x) mapa.set(+x[1], { n: +x[1], nome: x[2].trim(), escolha: x[3].trim() });
      } });
    return [...mapa.values()].sort((a, b) => a.n - b.n);
  }
  // As etapas também saem do próprio briefing pronto (uma por seção do documento): vale para briefing antigo e para quando o agente não registrou a linha
  const ETAPAS_BRIEFING = ['Núcleo de conversão', 'Dores', 'Desejos', 'Promessas', 'Soluções comuns', 'Crenças', 'Objeções', 'Narrativa da VSL', 'Nome chiclete', 'Provas', 'Elementos usados', 'Produto', 'Estrutura da VSL', 'Mecanismo'];      // as mesmas etapas da bíblia
  const ETAPAS_ANTIGAS = ['Sobre o expert', 'Promessas', 'Mecanismo do problema', 'Mecanismo da solução', 'Nome chiclete', 'Oferta', 'Bônus', 'Outline', 'One Belief'];      // briefing feito antes das etapas novas
  const FORA_DA_ESCOLHA = /^### (Opções da bíblia|Opções das bíblias|O que as bíblias pedem do expert|Estrutura das VSLs do nicho|Nomes do nicho|Sugestões|Como pesquisar mais nomes|Ofertas do nicho|Bônus do nicho)\s*$/m;
  function etapasDoDoc(doc) {
    const txt = String(doc || '').replace(/^---[\s\S]*?\n---\n/, ''), sec = {};
    txt.split(/^## /m).slice(1).forEach((b) => { const k = b.indexOf('\n'); sec[b.slice(0, k < 0 ? b.length : k).trim().toLowerCase()] = k < 0 ? '' : b.slice(k + 1); });
    const limpa = (x) => x.replace(/\*\*/g, '').replace(/^[“"]|[”"]$/g, '').trim();
    const out = [];
    const estrutura = (n) => n === 'Estrutura da VSL' || n === 'Outline';
    (sec['núcleo de conversão'] != null ? ETAPAS_BRIEFING : ETAPAS_ANTIGAS).forEach((nome, k) => {
      let bruto = sec[nome.toLowerCase()]; if (bruto == null) return;
      if (estrutura(nome)) { const k = bruto.search(/^### Estrutura desta VSL\s*$/m); if (k >= 0) bruto = bruto.slice(k).replace(/^### .*\n/, ''); }       // o cartão mostra a estrutura desta VSL, não a análise das outras
      const corte = bruto.search(FORA_DA_ESCOLHA), det = (corte >= 0 ? bruto.slice(0, corte) : bruto).trim();
      const linhas = det.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('>') && !l.startsWith('###'));
      let esc = '';
      if (nome === 'One Belief') esc = (linhas.find((l) => /^\*\*One Belief:\*\*/i.test(l)) || '').replace(/^\*\*One Belief:\*\*/i, '');
      else if (['Bônus', 'Provas', 'Crenças', 'Objeções'].includes(nome)) esc = linhas.filter((l) => l.startsWith('|') && !/^\|\s*-/.test(l)).slice(1).map((l) => l.split('|')[1]).filter((x) => x && x.trim()).map(limpa).join(' · ');
      else if (estrutura(nome)) { const t = linhas.find((l) => /^\|\s*\*{0,2}Total/i.test(l)); if (t) { const c = t.split('|').map(limpa); esc = c.slice(2).filter((x) => /\d/.test(x))[0] || ''; if (esc) esc = 'Total: ' + esc; } }
      if (!esc) esc = ((linhas.find((l) => /^-\s*\*\*Nome:\*\*\s*\S/.test(l)) || '').replace(/^-\s*\*\*Nome:\*\*/, '')) || (linhas.find((l) => /^-\s+\S/.test(l)) || linhas[0] || '').replace(/^-\s+/, '');
      esc = limpa(esc);
      // aberto, o cartão mostra a seção inteira, igual à do arquivo (não um resumo)
      if (esc || det) out.push({ n: k + 1, nome, escolha: esc || '(sem resumo)', detalhe: (sec[nome.toLowerCase()] || det).trim() });
    });
    return out;
  }
  function NoEtapa({ data }) {
    const aberta = !!data.aberta;
    const alternar = () => { api && api.etapa(data.chat, data.n, !aberta); setTimeout(() => forcar && forcar(), 0); };
    return html`<div class=${'an an-etapa' + (aberta ? ' aberta' : '')} onMouseDown=${() => api && api.etapa(data.chat, data.n)}>
      <${Handle} type="target" position=${Position.Left} isConnectable=${false} className="h-fixa vis" style=${{ top: 28 }} />
      <${Canto} minW=${220} minH=${aberta ? 140 : 56} />
      <div class="et-h" title="Arraste para mover">
        <span class="et-n">${data.n}</span>
        <div class="et-t"><b>${data.nome}</b><small>${data.escolha}</small></div>
        <button class="et-x nodrag" onClick=${alternar} title=${aberta ? 'Minimizar' : 'Maximizar'} aria-label=${aberta ? 'Minimizar' : 'Maximizar'}><${Ico} n=${aberta ? 'minimizar' : 'maximizar'} s=${13} /></button></div>
      ${aberta ? html`<div class="et-d md nodrag nowheel" dangerouslySetInnerHTML=${{ __html: ctx.md(data.detalhe || data.escolha) }}></div>` : null}
    </div>`;
  }
  /* cópia de um arquivo do chat, solta no flow (arrastada da lista de arquivos): nó próprio, com saída para ligar onde quiser.
     Minimizado é só o cartão; maximizado mostra o conteúdo. Fechar tira só a cópia: o arquivo continua no chat */
  function NoDoc({ id, data }) {
    const [perg, setPerg] = useState(false);
    const rfi = useReactFlow();
    const mini = !!data.mini, texto = data.texto || '';
    const tam = (v) => { setPerg(false); api && api.patch(id, { mini: v }); setTimeout(() => forcar && forcar(), 0); };
    return html`<div class=${'an an-doc ' + (mini ? 'an-trarq' : 'an-previa')} style=${mini ? { width: 'max-content', minWidth: '300px' } : { height: '640px' }}>
      <div class="an-head"><span class="an-ico"><${Ico} n="arquivo" s=${mini ? 17 : 18} /></span>
        <div class="an-t"><b title=${data.nome}>${data.nome}</b><small>${texto.length.toLocaleString('pt-BR')} caracteres · cópia</small></div>
        <button class="an-mini nodrag" onClick=${() => tam(true)} disabled=${mini} title="Minimizar" aria-label="Minimizar"><${Ico} n="minimizar" s=${14} /></button>
        <button class="an-mini nodrag" onClick=${() => tam(false)} disabled=${!mini} title="Maximizar" aria-label="Maximizar"><${Ico} n="maximizar" s=${14} /></button>
        <button class="an-mini nodrag" onClick=${() => setPerg(true)} title="Fechar" aria-label="Fechar"><${Ico} n="x" s=${15} /></button></div>
      ${perg ? html`<div class="doc-perg nodrag"><span>Fechar esta cópia? O arquivo continua na lista do chat.</span>
        <div><button class="cm-btn" onClick=${() => setPerg(false)}>Cancelar</button><button class="cm-btn forte" onClick=${() => rfi.deleteElements({ nodes: [{ id }] })}>Fechar</button></div></div>` : null}
      ${mini ? null : html`${data.md ? html`<div class="pv-corpo md nodrag nowheel" dangerouslySetInnerHTML=${{ __html: ctx.md(texto) }}></div>` : html`<div class="pv-corpo pv-texto nodrag nowheel">${texto}</div>`}
        <div class="pv-pe nodrag"><button class="cm-btn" onClick=${() => ctx.copiar(texto)}>Copiar</button></div>`}
      <${Handle} type="target" position=${Position.Left} style=${{ top: 26 }} title="Ligue um ChatGPT aqui, se ele vier antes dos arquivos" />
      <${Handle} type="source" position=${Position.Right} style=${{ top: 26 }} title="Ligue num chat, na Bíblia ou no Briefing para usar este arquivo" />
    </div>`;
  }

  /* YouTube: ligado a um chat, dá ao agente a busca de vídeos por termo (yt-dlp: sem login, sem navegador) */
  function NoYouTube({ id, selected }) {
    const info = ctx.info(id, 'youtube');
    return html`<div class=${'an ' + (selected ? 'an-on ' : '') + (info.rodando ? 'rodando' : '')}>
      <${Handle} type="target" position=${Position.Left} title="Entrada: o Blocos de VSL" />
      <${Cabeca} id=${id} tipo="youtube" titulo="YouTube" sub="Busca vídeos por termo" />
      <div class="an-body">
        <div class="an-status"><span class=${'dot ' + (info.estado || '')}></span>${info.chats ? (info.rodando ? 'Trabalhando no chat…' : 'Ligado ao chat: peça a busca por lá') : 'Ligue este nó a um Chat'}</div>
        <div class="an-vazio" style=${{ textAlign: 'left' }}>Ex.: "busque no YouTube vídeos de emagrecimento" ou "…os Shorts de emagrecimento". O chat traz os links com canal, visualizações e duração.</div>
      </div>
      <${Handle} type="source" position=${Position.Right} />
    </div>`;
  }

  /* Conteúdo das redes sociais: cola o link de um vídeo (YouTube, TikTok ou Instagram) e o nó mostra a miniatura e os dados.
     Ligado a um chat, o vídeo entra como contexto. A fala é transcrita sozinha logo depois de ler o link (legenda ou Whisper) e não aparece no nó: é para o chat */
  function NoSocial({ id, data, selected }) {
    const [url, setUrl] = useState(data.url || '');
    const i = data.info, st = data.status || '';
    const num = (n) => (n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '').replace('.', ',') + ' mi' : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, '').replace('.', ',') + ' mil' : String(n));
    const tempo = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    const ler = () => { const u = url.trim(); if (u && st !== 'lendo') ctx.socialLer(id, u); };
    // com o vídeo lido, o nó vira um cartão só com a faixa do título e a capa (a transcrição fica guardada, sem aparecer: é para o chat)
    const emPe = i && (i.vertical != null ? i.vertical : !!data.vertical);
    if (i) return html`<div class=${'an an-social soc-cartao ' + (emPe ? 'vert ' : '') + (selected ? 'an-on ' : '') + (data.transcrevendo ? 'rodando' : '')}>
      <div class="soc-h">${data.transcrevendo ? html`${['youtube', 'instagram', 'tiktok'].includes(i.rede) ? html`<span class="soc-hi"><img src=${'/rede-' + i.rede + '.png'} alt=${i.rede_nome} /></span>` : null}<span class="soc-pisca" aria-hidden="true"></span><b>Processando ${Math.round((data.progresso || 0) * 100)}%</b>`
          : html`<span class="soc-hi">${['youtube', 'instagram', 'tiktok'].includes(i.rede) ? html`<img src=${'/rede-' + i.rede + '.png'} alt=${i.rede_nome} />` : html`<${Ico} n="video" s=${16} />`}</span><b title=${i.titulo}>${i.titulo || 'Vídeo sem título'}</b>`}<${MenuNo} id=${id} itens=${[{ rot: 'Trocar o link', ico: 'social', fn: () => { setUrl(''); api && api.patch(id, { url: '', info: null, texto: '', erro: null, status: '', transcrevendo: false, semFala: false }); } }]} /></div>
      <a class="soc-thumb nodrag" href=${i.link} target="_blank" rel="noopener" title=${'Abrir no ' + i.rede_nome}>
        ${i.thumb ? html`<img src=${i.thumb} alt="" onLoad=${(e) => { if (i.vertical == null) { const v = e.target.naturalHeight > e.target.naturalWidth; if (v !== !!data.vertical) api && api.patch(id, { vertical: v }); } }} />` : html`<span class="soc-sem"><${Ico} n="video" s=${26} /></span>`}
        <span class="soc-play"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M8 5.500v13l11-6.500z" fill="currentColor"/></svg></span>
        ${!data.transcrevendo && data.semFala ? html`<span class="soc-st">Sem fala</span>` : null}</a>
      ${data.erro && !data.transcrevendo && !data.texto ? html`<button class="soc-er nodrag" onClick=${() => ctx.socialTranscrever(id)} title=${data.erro}>Não processou. Tentar de novo</button>` : null}
      <${Handle} type="source" position=${Position.Right} title="Ligue num Chat para usar este vídeo" />
    </div>`;
    return html`<div class=${'an an-social ' + (selected ? 'an-on ' : '') + (st === 'lendo' ? 'rodando' : '')}>
      <${Cabeca} id=${id} tipo="social" titulo="Conteúdo das redes sociais" sub="YouTube, TikTok ou Instagram" />
      <div class="an-body">
        <input class="soc-url nodrag" value=${url} placeholder="Cole o link do vídeo e aperte Enter" aria-label="Link do vídeo" disabled=${st === 'lendo'}
          onInput=${(e) => setUrl(e.target.value)} onKeyDown=${(e) => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); ler(); } }} onPaste=${(e) => { const t = (e.clipboardData && e.clipboardData.getData('text')) || ''; if (/^https:\/\//.test(t.trim())) { e.preventDefault(); setUrl(t.trim()); ctx.socialLer(id, t.trim()); } }} />
        ${st === 'lendo' ? html`<div class="an-status"><span class="dot"></span>Lendo o link…</div>`
          : data.erro ? html`<div class="an-erro">${data.erro}</div>`
          : html`<div class="an-vazio" style=${{ textAlign: 'left' }}>Aceita vídeo do YouTube, do TikTok e do Instagram. O nó mostra a capa e processa o vídeo sozinho. Ligue a um Chat e ele passa a saber o que é dito no vídeo.</div>`}
      </div>
      <${Handle} type="source" position=${Position.Right} title="Ligue num Chat para usar este vídeo" />
    </div>`;
  }

  /* Oferta: diz de qual projeto do cofre é o flow. Ligada ao chat, ele consulta as big ideas e os anúncios dela,
     e o Salvar no Cérebro já grava nessa oferta. */
  function NoOferta({ id, data, selected }) {
    const exps = ctx.projetosCofre();
    const ex = exps.find((x) => x.nome === data.expert);
    const [modo, setModo] = useState(null);                 // 'existente' | 'novo' (sem projetos no cofre, começa em novo)
    const [nExp, setNExp] = useState(''), [nOfe, setNOfe] = useState(''), [erro, setErro] = useState(''), [criando, setCriando] = useState(false);
    const m = modo || (exps.length ? 'existente' : 'novo');
    const set = (p) => { api && api.patch(id, p); setTimeout(() => forcar && forcar(), 0); };
    const criar = async () => {
      if (!nExp.trim() || !nOfe.trim()) { setErro('Diga o expert e a oferta.'); return; }
      setErro(''); setCriando(true);
      try { const r = await ctx.criarProjetoCofre(nExp.trim(), nOfe.trim()); set({ expert: r.expert, oferta: r.oferta }); setModo('existente'); setNExp(''); setNOfe(''); }
      catch (e) { setErro(e.message); }
      setCriando(false);
    };
    return html`<div class=${'an an-int ' + (selected ? 'an-on' : '')}>
      <${Cabeca} id=${id} tipo="oferta" titulo="Oferta" sub=${data.expert && data.oferta ? data.expert + ' · ' + data.oferta + (data.vsl ? ' · ' + data.vsl : '') : 'De qual projeto é este flow'} />
      <div class="an-body">
        <div class="of-seg nodrag"><button class=${m === 'existente' ? 'on' : ''} onClick=${() => setModo('existente')}>Existente</button><button class=${m === 'novo' ? 'on' : ''} onClick=${() => setModo('novo')}>Criar novo</button></div>
        ${m === 'existente'
          ? (exps.length ? html`<div class="of-campos nodrag">
              <select class="an-sel" value=${data.expert || ''} onChange=${(e) => { const x = exps.find((y) => y.nome === e.target.value); set({ expert: e.target.value, oferta: (x && x.ofertas[0]) || '' }); if (e.target.value) ctx.expertDoNo(e.target.value); }}>
                <option value="">Escolha o expert…</option>${exps.map((x) => html`<option key=${x.nome} value=${x.nome}>${x.nome}</option>`)}</select>
              <select class="an-sel" value=${data.oferta || ''} disabled=${!ex} onChange=${(e) => set({ oferta: e.target.value })}>
                <option value="">Escolha a oferta…</option>${(ex ? ex.ofertas : []).map((o) => html`<option key=${o} value=${o}>${o}</option>`)}</select>
              <select class="an-sel" value=${data.vsl || ''} disabled=${!data.oferta} onChange=${(e) => set({ vsl: e.target.value })} title="Para qual versão da VSL os anúncios deste flow mandam">
                <option value="">Versão da VSL…</option>${['V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8'].map((v) => html`<option key=${v} value=${v}>${v}</option>`)}</select>
            </div>` : html`<div class="an-vazio">Ainda não há projeto no cofre. Use "Criar novo".</div>`)
          : html`<div class="of-campos nodrag">
              <input class="an-sel of-in" list=${'ofx-' + id} placeholder="Nome do expert" value=${nExp} onChange=${(e) => setNExp(e.target.value)} />
              <datalist id=${'ofx-' + id}>${exps.map((x) => html`<option key=${x.nome} value=${x.nome} />`)}</datalist>
              <input class="an-sel of-in" placeholder="Nome da oferta" value=${nOfe} onChange=${(e) => setNOfe(e.target.value)} onKeyDown=${(e) => { if (e.key === 'Enter') criar(); }} />
              <small class="of-path">Cria no Cérebro: Projetos/${nExp.trim() || 'Expert'}/${nOfe.trim() || 'Oferta'}/</small>
              <button class="an-btn of-criar" onClick=${criar} disabled=${criando}>${criando ? 'Criando…' : 'Criar no Cérebro'}</button>
            </div>`}
        ${erro ? html`<div class="an-erro">${erro}</div>` : null}
        ${m === 'existente' && data.expert && data.oferta ? html`<div class="an-status"><span class="dot ok"></span>O chat consulta e grava nesta oferta</div>` : null}
      </div>
      <${Handle} type="source" position=${Position.Right} />
    </div>`;
  }

  /* Grupo: área redimensionável; as inteligências arrastadas para dentro viram um contexto só, ligado pela saída do grupo */
  function NoGrupo({ id, data, selected }) {
    const n = ctx.grupoQtd(id);
    const [ren, setRen] = useState(false);
    const gravar = (v) => { setRen(false); v = String(v || '').replace(/\s+/g, ' ').trim().slice(0, 60); if (api && v !== (data.nome || '')) api.patch(id, { nome: v }); };
    return html`<div class=${'an-grupo' + (selected ? ' an-on' : '')}>
      <${NodeResizeControl} position="bottom-right" minWidth=${320} minHeight=${200} className="an-resize" style=${{ background: 'transparent', border: 'none' }}>
        <span class="an-canto" title="Arraste para mudar o tamanho"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          ${[[12, 2], [8, 6], [12, 6], [4, 10], [8, 10], [12, 10]].map(([x, y]) => html`<circle key=${x + '-' + y} cx=${x} cy=${y} r="1.35" fill="currentColor" />`)}
        </svg></span>
      <//>
      <${Cabeca} id=${id} tipo="grupo" itens=${[{ rot: 'Renomear', ico: 'lapis', fn: () => setRen(true) }]}
        titulo=${ren ? html`<input class="gr-ren nodrag" autoFocus defaultValue=${data.nome || ''} placeholder="Nome do grupo" maxLength="60" aria-label="Nome do grupo"
          onKeyDown=${(e) => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); gravar(e.target.value); } else if (e.key === 'Escape') setRen(false); }}
          onBlur=${(e) => gravar(e.target.value)} />` : data.nome || 'Grupo'} sub=${n ? n + (n > 1 ? ' itens dentro' : ' item dentro') : 'Arraste inteligências e vídeos para dentro'} />
      <${Handle} type="source" position=${Position.Right} style=${{ top: 26 }} />
    </div>`;
  }

  /* Transcrição: sobe o vídeo, o Whisper transcreve no computador e o texto aparece num arquivo ao lado */
  function NoTranscricao({ id, data, selected }) {
    const fileRef = useRef(null);
    const st = data.status || '';
    const ocupado = ['enviando', 'na fila', 'transcrevendo'].includes(st);
    const pct = st === 'enviando' ? data.envio || 0 : Math.round((data.progresso || 0) * 100);
    const min = (s) => (s ? Math.floor(s / 60) + ':' + String(Math.round(s % 60)).padStart(2, '0') : '');
    const escolher = (e) => { const f = (e.target.files || [])[0]; e.target.value = ''; if (f) ctx.transcrever(id, f); };
    const rotulo = { enviando: 'Enviando o vídeo… ' + pct + '%', 'na fila': 'Na fila: esperando outra transcrição terminar', transcrevendo: 'Transcrevendo com o Whisper… ' + pct + '%' }[st];
    // pronta: o nó vira o bloco da transcrição (não transcreve outro vídeo). O ícone de vídeo abre o vídeo aqui mesmo, com a fala grifada
    const pronta = st === 'pronto' && !!data.arquivo;
    const sinc = pronta ? ctx.sincronia(id, data.arquivo) : null;
    const [k, setK] = useState(-1);
    const caixa = useRef(null);
    const vid = useRef(null);
    const comVideo = !!(pronta && data.trVideo && sinc && sinc.midia);
    useEffect(() => { if (pronta && data.trVideo && sinc && !sinc.erro && !sinc.midia) { ctx.aviso('O vídeo não está mais disponível para acompanhar a transcrição.'); api && api.patch(id, { trVideo: false }); } }, [pronta, data.trVideo, sinc]);
    useEffect(() => { if (!comVideo) setK(-1); }, [comVideo]);
    useEffect(() => { const b = caixa.current, at = b && k >= 0 ? b.querySelector('.tr-g.on') : null;
      if (at && !b.matches(':hover')) { const r = at.getBoundingClientRect(), q = b.getBoundingClientRect(); if (r.top < q.top + 20 || r.bottom > q.bottom - 30) b.scrollTop += r.top - q.top - q.height / 2; } }, [k]);
    if (pronta) {
      const g = (sinc && sinc.trechos) || [], pars = g.length ? ctx.trParagrafos({ trechos: g }) : [];
      const texto = pars.map((p) => p.map((i) => g[i].texto).join(' ')).join('\n\n');
      const seguir = (e) => { const t = e.target.currentTime; let lo = 0, hi = g.length - 1, a = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (g[m].ini <= t + 0.05) { a = m; lo = m + 1; } else hi = m - 1; } if (a !== k) setK(a); };
      const ir = (i) => { const v = vid.current; if (comVideo && v) { v.currentTime = g[i].ini + 0.01; v.play().catch(() => {}); } };
      const nome = String(data.video || data.arquivo).replace(/\.[a-z0-9]{2,4}$/i, '');
      return html`<div class=${'an an-tr an-trp ' + (selected ? 'an-on ' : '') + (comVideo ? 'com-video' : '')}>
        <${Cabeca} id=${id} tipo="transcricao" titulo=${html`<span title=${nome}>${nome}</span>`} sub=${'Transcrição' + (data.duracao ? ' · ' + min(data.duracao) : '') + ' · ' + (data.chars || 0).toLocaleString('pt-BR') + ' caracteres'}
          extra=${html`<button class=${'an-mini nodrag' + (data.trVideo ? ' on' : '')} onClick=${() => api && api.patch(id, { trVideo: !data.trVideo })} aria-pressed=${!!data.trVideo}
            title=${data.trVideo ? 'Fechar o vídeo' : 'Ver o vídeo com a transcrição acompanhando'} aria-label="Ver o vídeo com a transcrição"><${Ico} n="video" s=${15} /></button>`} />
        ${comVideo ? html`<div class="trp-midia nodrag">${sinc.audio
          ? html`<audio ref=${vid} controls preload="metadata" src=${sinc.src} onTimeUpdate=${seguir} onSeeked=${seguir}></audio>`
          : html`<video ref=${vid} controls playsInline preload="metadata" src=${sinc.src} onTimeUpdate=${seguir} onSeeked=${seguir} onError=${() => { ctx.aviso('O vídeo não está mais disponível para acompanhar a transcrição.'); api && api.patch(id, { trVideo: false }); }}></video>`}</div>` : null}
        <div class="trp-texto nodrag nowheel" ref=${caixa}>${!sinc ? 'Carregando…' : sinc.erro ? sinc.erro
          : pars.map((p, n) => html`<p key=${n}>${p.map((i) => html`<span key=${i} class=${'tr-g' + (i === k ? ' on' : '') + (comVideo ? '' : ' parado')} onClick=${() => ir(i)}>${g[i].texto} </span>`)}</p>`)}</div>
        <div class="pv-pe nodrag"><button class="cm-btn" disabled=${!texto} onClick=${() => texto && ctx.copiar(texto)}>Copiar</button></div>
        <${Handle} type="source" position=${Position.Right} style=${{ top: 26 }} title="Ligue onde quiser usar a transcrição" />
      </div>`;
    }
    return html`<div class=${'an an-tr ' + (selected ? 'an-on ' : '') + (ocupado ? 'rodando' : '')}>
      <${Cabeca} id=${id} tipo="transcricao" titulo="Transcrição" sub=${data.video ? data.video : 'Vídeo ou áudio em texto, de graça'} />
      <div class="an-body">
        ${ocupado ? html`<div class="tr-prog"><span>${rotulo}</span><div class="tr-barra"><i style=${{ width: Math.max(3, pct) + '%' }}></i></div>
            ${data.duracao ? html`<small>Vídeo de ${min(data.duracao)} · roda no seu computador</small>` : null}</div>`
          : st === 'erro' ? html`<div class="an-erro">${data.erro || 'Não deu para transcrever.'}</div>`
          : html`<div class="an-vazio">Suba um vídeo ou áudio (mp4, mov, mp3, m4a…). O Whisper transcreve aqui no computador, sem gastar o ChatGPT. Quando terminar, este nó vira a transcrição.</div>`}
      </div>
      <button class="an-btn nodrag" onClick=${() => fileRef.current && fileRef.current.click()} disabled=${ocupado}>
        <${Ico} n="upload" s=${14} />${ocupado ? 'Transcrevendo…' : 'Subir vídeo'}</button>
      ${ocupado ? html`<button class="an-btn nodrag" style=${{ marginTop: '6px', background: 'transparent', border: '1px solid var(--line, rgba(255,255,255,.14))', color: 'var(--muted, #9a9aa3)' }} onClick=${() => ctx.cancelarTranscricao(id)}><${Ico} n="x" s=${14} />Cancelar</button>` : null}
      <input ref=${fileRef} type="file" hidden accept="video/*,audio/*,.mkv" onChange=${escolher} />
    </div>`;
  }

  /* o arquivo da transcrição: pequeno ao lado do nó; maximizado mostra o texto. Tem saída própria para ligar onde quiser */
  function NoTrArq({ data }) {
    const grande = !!data.grande;
    const texto = grande ? ctx.textoTranscricao(data.no, data.arquivo) : null;
    const alternar = () => { api && api.patch(data.no, { trGrande: !grande }); setTimeout(() => forcar && forcar(), 0); };
    return html`<div class=${'an an-trarq' + (grande ? ' grande' : '')} style=${{ height: data.h + 'px' }}>
      <svg class="pv-linha" width="73" height="14" viewBox="0 0 73 14" aria-hidden="true"><path d="M6 7H67" /><circle cx="0" cy="7" r="5.25"/><circle cx="73" cy="7" r="5.25"/></svg>
      <div class="an-head"><span class="an-ico"><${Ico} n="arquivo" s=${17} /></span>
        <div class="an-t"><b title=${data.arquivo}>${data.arquivo.replace(/\.srt$/, '')}</b><small>${(data.chars || 0).toLocaleString('pt-BR')} caracteres · transcrição</small></div>
        <button class="an-mini nodrag" onClick=${() => ctx.verSincronia(data.no, data.arquivo)} title="Ver o vídeo com a transcrição acompanhando" aria-label="Ver o vídeo com a transcrição"><${Ico} n="video" s=${14} /></button>
        <button class="an-mini nodrag" onClick=${alternar} title=${grande ? 'Diminuir' : 'Ver a transcrição'} aria-label=${grande ? 'Diminuir' : 'Maximizar'}><${Ico} n=${grande ? 'minimizar' : 'maximizar'} s=${14} /></button></div>
      ${grande ? html`<div class="pv-corpo pv-texto nodrag nowheel">${texto == null ? 'Carregando…' : texto}</div>
        <div class="pv-pe nodrag"><button class="cm-btn" onClick=${() => texto && ctx.copiar(texto)}>Copiar</button></div>` : null}
      <${Handle} type="source" position=${Position.Right} style=${{ top: 26 }} title="Ligue onde quiser usar a transcrição" />
    </div>`;
  }

  /* Inteligência em texto: só o campo de escrever ou colar */
  function NoTexto({ id, data, selected, parentId }) {
    const [texto, setTexto] = useState(data.texto || '');
    useEffect(() => { setTexto(data.texto || ''); }, [data.texto]);
    const salvar = () => { if (texto !== (data.texto || '') && api) api.patch(id, { texto }); };
    const chars = texto.trim().length;
    // dentro do conjunto da Bíblia da VSL: o que for colado aqui vira um arquivo de VSL embaixo, com a saída própria para ligar no chat
    if (data.modo === 'vsl') {
      const criar = (t) => { t = (t || '').trim(); if (!t) return; api && api.novaVsl(id, t); setTexto(''); api && api.patch(id, { texto: '' }); };
      return html`<div class=${'an an-int ' + (selected ? 'an-on' : '')}>
        <${Handle} type="target" position=${Position.Left} />
        <${Cabeca} id=${id} tipo="inteligencia" titulo="Inteligência em texto" sub="Cole a VSL: ela vira um arquivo embaixo" />
        <div class="an-body">
          <textarea class="an-txt nodrag nowheel" placeholder="Cole aqui a transcrição da VSL…" value=${texto}
            onChange=${(e) => setTexto(e.target.value)} onPaste=${(e) => { const t = (e.clipboardData && e.clipboardData.getData('text')) || ''; if (t.trim().length > LONGO) { e.preventDefault(); criar(t); } }}></textarea>
          ${chars ? html`<button class="cm-btn forte nodrag" style=${{ marginTop: '8px' }} onClick=${() => criar(texto)}>Criar o arquivo da VSL</button>` : null}
        </div>
      </div>`;
    }
    return html`<div class=${'an an-int ' + (selected ? 'an-on' : '')}>
      ${parentId ? null : html`<${Handle} type="target" position=${Position.Left} />`}
      <${Cabeca} id=${id} tipo="inteligencia" titulo="Inteligência em texto" sub=${chars ? chars.toLocaleString('pt-BR') + ' caracteres' : 'Texto de contexto'} />
      <div class="an-body">
        <textarea class="an-txt nodrag nowheel" placeholder="Escreva ou cole aqui: briefing, anotações, transcrição…" value=${texto}
          onChange=${(e) => setTexto(e.target.value)} onBlur=${salvar}></textarea>
      </div>
      ${parentId ? null : html`<${Handle} type="source" position=${Position.Right} />`}
    </div>`;
  }

  /* Arquivo de VSL: nasce do texto colado na Inteligência em texto do conjunto da Bíblia. Mostra em que parte a bíblia dela está */
  function NoVsl({ id, data, selected }) {
    const [edit, setEdit] = useState(false);
    const [nome, setNome] = useState(data.nome || 'VSL');
    const info = ctx.vslInfo ? ctx.vslInfo(id) : { feitas: 0, total: 7, proxima: '' };
    const gravar = () => { setEdit(false); const n = nome.trim(); if (n && n !== data.nome) api && api.patch(id, { nome: n }); else setNome(data.nome || 'VSL'); };
    const etapa = info.feitas >= info.total ? 'Bíblia completa' : info.feitas ? `Parte ${info.feitas} de ${info.total} pronta · próxima: ${info.proxima}` : `Nenhuma parte ainda · ${info.total} partes`;
    return html`<div class=${'an an-doc an-trarq an-vsl ' + (selected ? 'an-on' : '')} style=${{ width: '300px' }}>
      <div class="an-head"><span class="an-ico"><${Ico} n="arquivo" s=${17} /></span>
        <div class="an-t">${edit
          ? html`<input class="an-ren nodrag" autoFocus value=${nome} onChange=${(e) => setNome(e.target.value)} onBlur=${gravar} onKeyDown=${(e) => { if (e.key === 'Enter') gravar(); if (e.key === 'Escape') { setNome(data.nome || 'VSL'); setEdit(false); } }} aria-label="Nome do arquivo" />`
          : html`<b title=${data.nome}>${data.nome}</b>`}
          <small>${(data.texto || '').length.toLocaleString('pt-BR')} caracteres</small></div>
        <${MenuNo} id=${id} itens=${[{ rot: 'Renomear', ico: 'ajustar', fn: () => setEdit(true) }]} /></div>
      <div class="vsl-etapa"><span class="vsl-barra"><i style=${{ width: Math.round((info.feitas / info.total) * 100) + '%' }}></i></span><small>${etapa}</small></div>
      <${Handle} type="source" position=${Position.Right} style=${{ top: 26 }} title="Ligue no chat da Bíblia da VSL (uma VSL por vez)" />
    </div>`;
  }

  /* Inteligência em arquivo: só arquivos e imagens */
  /* Fontes do Blocos de VSL: cada uma é um nó próprio (tese, bíblias, VSLs de referência), ligado ao agente. Nascem juntas, já interligadas, quando o Blocos de VSL é arrastado para o flow */
  const FONTES = {
    tese: { titulo: 'Briefing de tese', sub: 'A tese desta VSL', ico: 'briefing' },
    biblias: { titulo: 'Bíblias de VSL', sub: 'Até três bíblias', ico: 'biblia' },
    vsls: { titulo: 'VSLs de referência', sub: 'Transcrições para ver como cada bloco foi escrito', ico: 'arquivo' },
  };
  function NoFonte({ id, data, selected }) {
    const papel = FONTES[data.papel] ? data.papel : 'vsls', F = FONTES[papel];
    const [enviando, setEnviando] = useState(false);
    const [erro, setErro] = useState('');
    const fileRef = useRef(null);
    const salvar = (patch) => api && api.patch(id, patch);
    const slots = [0, 1, 2].map((i) => (data.slots || [])[i] || null);
    const mudar = (i, v) => { const n = [...slots]; n[i] = v; salvar({ slots: n }); };
    const arqs = data.arquivos || [];
    const escolher = async (e) => {
      const fs = [...(e.target.files || [])]; e.target.value = '';
      setErro(''); setEnviando(true);
      try { const novos = []; for (const f of fs) novos.push(await ctx.enviarArquivo(id, f)); salvar({ arquivos: [...arqs.filter((a) => !novos.some((n) => n.nome === a.nome)), ...novos] }); }
      catch (err) { setErro(err.message); }
      setEnviando(false);
    };
    const remover = async (nome) => { await ctx.removerArquivo(id, nome); salvar({ arquivos: arqs.filter((a) => a.nome !== nome) }); };
    const lig = ctx.ligadosEm ? ctx.ligadosEm(id) : 0;
    const sub = lig ? lig + (lig > 1 ? ' arquivos ligados pelo flow' : ' arquivo ligado pelo flow') : papel === 'tese' ? (data.tese ? 'Tese carregada' : F.sub) : papel === 'biblias' ? (slots.filter(Boolean).length ? slots.filter(Boolean).length + ' de 3 carregadas' : F.sub) : (arqs.length ? arqs.length + (arqs.length > 1 ? ' transcrições' : ' transcrição') : F.sub);
    return html`<div class=${'an an-brief an-fonte ' + (selected ? 'an-on' : '')}>
      <${Handle} type="target" position=${Position.Left} title="Entrada: o Blocos de VSL" />
      <${Cabeca} id=${id} tipo=${F.ico} titulo=${F.titulo} sub=${sub} />
      <div class="an-body">
        ${papel === 'tese' ? html`<div class="an-slots"><${CampoBiblia} id=${id} k=${0} slot=${data.tese || null} biblias=${ctx.briefings()} mudar=${(v) => salvar({ tese: v })} /></div>` : null}
        ${papel === 'biblias' ? html`<div class="an-slots">${slots.map((sl, i) => html`<${CampoBiblia} key=${i} id=${id} k=${i} slot=${sl} biblias=${ctx.biblias()} mudar=${(v) => mudar(i, v)} />`)}</div>` : null}
        ${papel === 'vsls' ? html`${arqs.length ? html`<div class="an-files nodrag">${arqs.map((a) => html`<div class="an-file" key=${a.nome}>
            <${Ico} n="arquivo" s=${14} /><span title=${a.nome}>${a.nome}</span><small>${(a.caracteres || 0).toLocaleString('pt-BR')} car.</small>
            <button onClick=${() => remover(a.nome)} aria-label="Tirar a VSL"><${Ico} n="x" s=${12} /></button></div>`)}</div>`
            : html`<div class="an-vazio">Suba as transcrições das VSLs (.txt, .srt, .vtt, .md). O que o agente trouxer do YouTube também entra aqui.</div>`}
          ${erro ? html`<div class="an-erro">${erro}</div>` : null}` : null}
      </div>
      ${papel === 'vsls' ? html`<button class="an-btn nodrag" onClick=${() => fileRef.current && fileRef.current.click()} disabled=${enviando}><${Ico} n="upload" s=${14} />${enviando ? 'Enviando…' : 'Subir transcrição de VSL'}</button>
        <input ref=${fileRef} type="file" multiple hidden accept=".txt,.md,.srt,.vtt,.json" onChange=${escolher} />` : null}
      <${Handle} type="source" position=${Position.Right} />
    </div>`;
  }

  function NoArquivo({ id, data, selected, parentId }) {
    const [enviando, setEnviando] = useState(false);
    const [erro, setErro] = useState('');
    const fileRef = useRef(null);
    const salvar = (patch) => api && api.patch(id, patch);
    const escolher = async (e) => {
      const fs = [...(e.target.files || [])]; e.target.value = '';
      setErro(''); setEnviando(true);
      try {
        const novos = [];
        for (const f of fs) novos.push(await ctx.enviarArquivo(id, f));
        salvar({ arquivos: [...(data.arquivos || []).filter((a) => !novos.some((n) => n.nome === a.nome)), ...novos] });
      } catch (err) { setErro(err.message); }
      setEnviando(false);
    };
    const remover = async (nome) => { await ctx.removerArquivo(id, nome); salvar({ arquivos: (data.arquivos || []).filter((a) => a.nome !== nome) }); };
    const qtd = (data.arquivos || []).length;
    return html`<div class=${'an an-int ' + (selected ? 'an-on' : '')}>
      ${parentId ? null : html`<${Handle} type="target" position=${Position.Left} />`}
      <${Cabeca} id=${id} tipo="arquivo" titulo="Inteligência em arquivo" sub=${qtd ? qtd + (qtd > 1 ? ' arquivos' : ' arquivo') : 'Arquivos e imagens de contexto'} />
      <div class="an-body">
        ${qtd ? html`<div class="an-files nodrag">${data.arquivos.map((a) => html`<div class="an-file" key=${a.nome}>
          <${Ico} n=${a.imagem ? 'imagem' : 'arquivo'} s=${14} /><span title=${a.nome}>${a.nome}</span>
          <small>${a.imagem ? Math.round(a.bytes / 1024) + ' KB' : (a.caracteres || 0).toLocaleString('pt-BR') + ' car.'}</small>
          <button onClick=${() => remover(a.nome)} aria-label="Tirar arquivo"><${Ico} n="x" s=${12} /></button></div>`)}</div>`
        : html`<div class="an-vazio">Transcrições (.txt, .srt, .vtt, .json), textos (.md, .csv) e imagens (.png, .jpg, .webp).</div>`}
        ${erro ? html`<div class="an-erro">${erro}</div>` : null}
      </div>
      <button class="an-btn nodrag" onClick=${() => fileRef.current && fileRef.current.click()} disabled=${enviando}>
        <${Ico} n="upload" s=${14} />${enviando ? 'Enviando…' : 'Subir arquivo ou imagem'}</button>
      <input ref=${fileRef} type="file" multiple hidden accept=".txt,.md,.srt,.vtt,.json,.csv,.png,.jpg,.jpeg,.webp" onChange=${escolher} />
      ${parentId ? null : html`<${Handle} type="source" position=${Position.Right} />`}
    </div>`;
  }

  function NoChatGPT({ id, data, selected }) {
    const ms = ctx.gpt().modelos || [], padrao = (ms.find((m) => m.padrao) || ms[0] || {}).id;
    const atual = ms.some((m) => m.id === data.modelo) ? data.modelo : padrao;
    return html`<div class=${'an-bola ' + (selected ? 'an-on' : '')} title="ChatGPT">
      <span class="an-bola-c"><${Ico} n="chatgpt" s=${24} /></span>
      ${ms.length ? html`<label class="an-bola-mod nodrag" title="Modelo usado pelos chats ligados a este ChatGPT">
          <select value=${atual} onChange=${(e) => { api && api.patch(id, { modelo: e.target.value }); setTimeout(() => forcar && forcar(), 0); }}>
            ${ms.map((m) => html`<option key=${m.id} value=${m.id}>${m.nome}${m.padrao ? ' (padrão)' : ''}</option>`)}</select>
          <span>${(ms.find((m) => m.id === atual) || {}).nome}</span><svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></label>`
        : html`<span class="an-bola-t">ChatGPT</span>`}
      <div class="an-bola-menu"><${MenuNo} id=${id} /></div>
      <${Handle} type="target" position=${Position.Left} title="Ligue uma Oferta aqui: os chats depois deste ChatGPT ficam presos a ela" />
      <${Handle} type="source" position=${Position.Right} />
    </div>`;
  }

  /* Nota: um título e uma anotação soltos no flow, para organizar. Não se liga em nada e não vai para o chat */
  function NoNota({ id, data, selected }) {
    const [tit, setTit] = useState(data.titulo || '');
    const [txt, setTxt] = useState(data.texto || '');
    useEffect(() => { setTit(data.titulo || ''); setTxt(data.texto || ''); }, [data.titulo, data.texto]);
    const area = useRef(null);
    useEffect(() => { const a = area.current; if (a) { a.style.height = 'auto'; a.style.height = a.scrollHeight + 'px'; } }, [txt]);
    const gravar = () => { if (api && (tit !== (data.titulo || '') || txt !== (data.texto || ''))) api.patch(id, { titulo: tit, texto: txt }); };
    return html`<div class=${'an-nota' + (selected ? ' an-on' : '')}>
      <div class="nt-topo"><input class="nt-tit nodrag" value=${tit} placeholder="Título" maxLength="80" aria-label="Título da nota"
        onInput=${(e) => setTit(e.target.value)} onBlur=${gravar} onKeyDown=${(e) => { e.stopPropagation(); if (e.key === 'Enter') e.target.blur(); }} /><${MenuNo} id=${id} /></div>
      <textarea ref=${area} class="nt-txt nodrag nowheel" rows="1" value=${txt} placeholder="Anotação (opcional)" aria-label="Texto da nota"
        onInput=${(e) => setTxt(e.target.value)} onBlur=${gravar} onKeyDown=${(e) => e.stopPropagation()}></textarea>
    </div>`;
  }

  const nodeTypes = { biblia: NoAgente, briefing: NoAgente, blocos: NoAgente, fonte: NoFonte, chat: NoChat, previa: NoPrevia, etapa: NoEtapa, doc: NoDoc, vsl: NoVsl, grupo: NoGrupo, oferta: NoOferta, youtube: NoYouTube, social: NoSocial, nota: NoNota, transcricao: NoTranscricao, trarq: NoTrArq, inteligencia: NoTexto, arquivo: NoArquivo, chatgpt: NoChatGPT };

  function Barra({ adicionar, temIA, area, sel, setSel, marcados, excluirMarcados }) {
    const item = (t, rot) => {
      const bloq = t !== 'chatgpt' && t !== 'transcricao' && t !== 'biblia' && t !== 'nota' && !(t === 'chat' && area === 'criativos') && !temIA;      // em Criativos o chat já traz o ChatGPT e a Oferta
      return html`<button class=${'fb-btn fb-' + t + (bloq ? ' bloq' : '')} draggable=${bloq ? 'false' : 'true'} disabled=${bloq}
        onDragStart=${(e) => { e.dataTransfer.setData('application/atlas-no', t); e.dataTransfer.effectAllowed = 'move'; }}
        onClick=${() => adicionar(t)} aria-label=${'Adicionar ' + rot}>
        <span class="fb-ico"><${Ico} n=${t} s=${t === 'chatgpt' ? 17 : 19} /></span><span class="fb-tip">${bloq ? 'Coloque o ChatGPT primeiro' : rot}</span></button>`;
    };
    // cada aba tem a sua barra: a VSL tem os agentes Bíblia e Briefing; em Criativos o chat já é o agente de anúncio. Os nós Oferta e YouTube existem nas duas
    const meio = area === 'criativos'
      ? [['oferta', 'Oferta'], ['inteligencia', 'Inteligência em texto'], ['arquivo', 'Inteligência em arquivo'], ['youtube', 'YouTube'], ['social', 'Redes sociais'], ['chat', 'Octopus Chat'], ['grupo', 'Grupo'], ['nota', 'Nota']]
      : [['oferta', 'Oferta'], ['inteligencia', 'Inteligência em texto'], ['arquivo', 'Inteligência em arquivo'], ['biblia', 'Bíblia da VSL'], ['briefing', 'Briefing de tese'], ['blocos', 'Blocos de VSL'], ['youtube', 'YouTube'], ['social', 'Redes sociais'], ['chat', 'Octopus Chat'], ['grupo', 'Grupo'], ['nota', 'Nota']];
    return html`<${Panel} position="top-left" className="fbar">
      ${item('chatgpt', 'ChatGPT')}<span class="fb-sep"></span>${meio.map(([t, r]) => item(t, r))}<span class="fb-sep"></span>${item('transcricao', 'Transcrição')}
      <span class="fb-sep"></span>
      <button class=${'fb-btn fb-selecao' + (sel ? ' on' : '')} onClick=${() => setSel(!sel)} aria-pressed=${sel} aria-label="Selecionar vários nós">
        <span class="fb-ico"><${Ico} n="selecao" s=${19} /></span><span class="fb-tip">${sel ? 'Seleção ligada: arraste no fundo para marcar vários nós e mova todos juntos. Clique para sair (ou Esc)' : 'Selecionar vários nós para mover juntos'}</span></button>
      ${sel && marcados ? html`<button class="fb-btn fb-lixo" onClick=${excluirMarcados} aria-label=${'Excluir os ' + marcados + ' nós selecionados'}>
        <span class="fb-ico"><${Ico} n="lixo" s=${18} /></span><span class="fb-n">${marcados}</span><span class="fb-tip">Excluir ${marcados === 1 ? 'o nó selecionado' : 'os ' + marcados + ' nós selecionados'}</span></button>` : null}
    <//>`;
  }

  function Canvas({ flow }) {
    const ordenar = (ns) => [...ns.filter((n) => n.type === 'grupo'), ...ns.filter((n) => n.type !== 'grupo')];
    const [nodes, setNodes, onNodesChange] = useNodesState(ordenar((flow.nodes || []).map((n) => (n.type === 'tiktok' ? { ...n, type: 'youtube' } : n)).map((n) => (n.type === 'chat' && !n.width ? { ...n, width: 380, height: 520 } : n.type === 'grupo' && !n.width ? { ...n, width: 460, height: 320 } : n))));
    const [edges, setEdges, onEdgesChange] = useEdgesState((flow.edges || []).map((e) => ({ ...e, source: String(e.source).startsWith('tr-') ? String(e.source).slice(3) : e.source, type: 'atlas' })));      // flows antigos: a transcrição saía de um arquivo ao lado ("tr-…"); agora sai do próprio nó
    const [, setTick] = useState(0);
    // modo seleção: arrastar no fundo não move o flow, desenha a área que marca os nós; os marcados são movidos todos juntos
    const [sel, setSel] = useState(false);
    useEffect(() => { if (!sel) return; const esc = (e) => { if (e.key === 'Escape') setSel(false); }; document.addEventListener('keydown', esc); return () => document.removeEventListener('keydown', esc); }, [sel]);
    useEffect(() => { if (!sel) setNodes((ns) => (ns.some((n) => n.selected) ? ns.map((n) => (n.selected ? { ...n, selected: false } : n)) : ns)); }, [sel]);
    const rf = useReactFlow();
    const nRef = useRef(nodes), eRef = useRef(edges);
    nRef.current = nodes; eRef.current = edges;

    // os nós do React Flow são memorizados: para mostrarem estado de fora (conversa, conta, bíblias),
    // cada atualização externa entrega um objeto de dados novo a todos eles
    useEffect(() => { forcar = () => setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data } }))); return () => { forcar = null; }; }, []);
    useEffect(() => { flow.nodes = nodes.map(({ id, type, position, data, width, height, parentId }) => ({ id, type, position, data, ...(type === 'chat' || type === 'grupo' ? { width, height } : {}), ...(parentId ? { parentId } : {}) })); ctx.salvar(); }, [nodes]);
    useEffect(() => { flow.edges = edges.map(({ id, source, target }) => ({ id, source, target })); ctx.salvar(); setTick((t) => t + 1); }, [edges]);

    api = {
      patch: (id, patch) => setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n))),
      // cartão de etapa: traz para a frente (o último mexido fica por cima) e, se pedido, abre ou fecha
      etapa: (chat, n, abrir) => setNodes((ns) => ns.map((x) => { if (x.id !== chat) return x;
        const ordem = (x.data.etapasOrdem || []), jaTopo = ordem[ordem.length - 1] === n;
        let abertas = x.data.etapasAbertas || [];
        if (abrir === true && !abertas.includes(n)) abertas = [...abertas, n]; else if (abrir === false) abertas = abertas.filter((k) => k !== n);
        if (jaTopo && abertas === (x.data.etapasAbertas || [])) return x;
        return { ...x, data: { ...x.data, etapasOrdem: [...ordem.filter((k) => k !== n), n], etapasAbertas: abertas } }; })),
      // texto colado na Inteligência do conjunto da Bíblia: vira um arquivo de VSL logo abaixo dela
      novaVsl: (de, texto) => setNodes((ns) => { const pai = ns.find((n) => n.id === de); if (!pai) return ns;
        const irmas = ns.filter((n) => n.type === 'vsl' && n.data.de === de), h = (pai.measured && pai.measured.height) || 190;
        const y = irmas.length ? Math.max(...irmas.map((n) => n.position.y)) + 92 : pai.position.y + h + 22;
        return ordenar([...ns, { id: 'vsl' + Math.random().toString(36).slice(2, 9), type: 'vsl', position: { x: pai.position.x, y }, data: { nome: 'VSL ' + (irmas.length + 1), texto, de, partes: {} } }]); }),
      // VSL colada direto no chat da Bíblia: vira o arquivo de VSL ao lado do chat, já ligado nele (é o que liga o modo por partes)
      vslDoChat: (chatId, idVsl, texto) => {
        setNodes((ns) => { const chat = ns.find((n) => n.id === chatId); if (!chat || ns.some((n) => n.id === idVsl)) return ns;
          const irmas = ns.filter((n) => n.type === 'vsl');
          return ordenar([...ns, { id: idVsl, type: 'vsl', position: { x: chat.position.x - 300, y: chat.position.y + 40 + irmas.length * 92 }, data: { nome: 'VSL ' + (irmas.length + 1), texto, de: null, partes: {} } }]); });
        setEdges((es) => addEdge({ source: idVsl, target: chatId, type: 'atlas', id: 'e' + Math.random().toString(36).slice(2, 9) }, es));
      },
      ligacoes: () => ({ nodes: nRef.current, edges: eRef.current }),
      enquadrar: () => rf.fitView({ duration: 300, padding: 0.3 }),
      mostrar: (ids, tentativa = 0) => {
        const ok = ids.every((id) => { const n = rf.getNode(id); return n && n.measured && n.measured.width; });
        if (!ok && tentativa < 20) { setTimeout(() => api && api.mostrar(ids, tentativa + 1), 100); return; }
        rf.fitView({ nodes: ids.map((id) => ({ id })), duration: 450, padding: 0.12, maxZoom: 1 });
      },
      // espera o nó ser medido (o React Flow só enquadra nós com tamanho conhecido)
      focar: (id, tentativa = 0) => {
        const n = rf.getNode(id);
        if (!n) return;
        if (!(n.measured && n.measured.width) && tentativa < 20) { setTimeout(() => api && api.focar(id, tentativa + 1), 100); return; }
        rf.setNodes((ns) => ns.map((x) => ({ ...x, selected: x.id === id })));
        rf.fitView({ nodes: [{ id }], duration: 400, padding: 0.6, maxZoom: 1.1 });
      },
    };

    const achaNo = (id) => nRef.current.find((n) => n.id === id) || (/^(pv|tr)-/.test(String(id)) ? rf.getNode(id) : null);
    const valida = useCallback((c) => {
      const s = achaNo(c.source), t = achaNo(c.target);
      if (!(s && t && s.id !== t.id && (ACEITA[t.type] || []).includes(s.type) && !eRef.current.some((e) => e.source === s.id && e.target === t.id))) return false;
      // não deixa fechar ciclo: o destino não pode já estar antes da origem
      const antes = new Set([s.id]), fila = [s.id];
      while (fila.length) { const x = fila.pop(); for (const e of eRef.current) if (e.target === x && !antes.has(e.source)) { antes.add(e.source); fila.push(e.source); } }
      return !antes.has(t.id);
    }, []);
    const AGENTE = { biblia: true, briefing: true, blocos: true };
    const onConnect = useCallback((c) => {
      const s = achaNo(c.source), t = achaNo(c.target);
      // um agente por chat: o chat faz só a tarefa do agente ligado nele
      if (s && t && t.type === 'chat' && AGENTE[s.type]) {
        const outro = eRef.current.map((e) => e.target === t.id && nRef.current.find((n) => n.id === e.source)).find((n) => n && AGENTE[n.type]);
        if (outro) { ctx.aviso('Um agente por chat. Este chat já faz ' + TIPOS[outro.type].nome + '. Tire a ligação dele ou use outro chat.'); return; }
      }
      // uma VSL por vez no chat: a bíblia é de uma VSL só
      if (s && t && t.type === 'chat' && s.type === 'vsl' && eRef.current.some((e) => e.target === t.id && (nRef.current.find((n) => n.id === e.source) || {}).type === 'vsl')) {
        ctx.aviso('Uma VSL por vez. Tire a ligação da outra VSL antes de ligar esta.'); return; }
      setEdges((es) => addEdge({ ...c, type: 'atlas', id: 'e' + Math.random().toString(36).slice(2, 9) }, es));
    }, []);

    const dadosIniciais = (tipo) => (tipo === 'inteligencia' ? { texto: '' } : tipo === 'arquivo' ? { arquivos: [] } : tipo === 'chat' ? { memoria: true } : {});
    // Blocos de VSL nasce como um conjunto, nesta ordem: o agente → as fontes (tese, bíblias, VSLs de referência, YouTube) → o chat.
    // O ChatGPT não vem ligado: a pessoa liga no Blocos de VSL e ele vale para o conjunto inteiro (o motor é achado em qualquer ponto antes do chat)
    const criarBlocos = (pos) => {
      const rid = (p) => p + Math.random().toString(36).slice(2, 9);
      const ag = rid('blo'), tese = rid('fon'), bib = rid('fon'), vsl = rid('fon'), yt = rid('you'), chat = rid('cha');
      const novos = [
        { id: ag, type: 'blocos', position: { x: pos.x, y: pos.y + 300 }, data: {} },
        { id: tese, type: 'fonte', position: { x: pos.x + 360, y: pos.y }, data: { papel: 'tese', tese: null } },
        { id: bib, type: 'fonte', position: { x: pos.x + 360, y: pos.y + 170 }, data: { papel: 'biblias', slots: [null, null, null] } },
        { id: vsl, type: 'fonte', position: { x: pos.x + 360, y: pos.y + 430 }, data: { papel: 'vsls', arquivos: [] } },
        { id: yt, type: 'youtube', position: { x: pos.x + 360, y: pos.y + 640 }, data: {} },
        { id: chat, type: 'chat', position: { x: pos.x + 760, y: pos.y + 120 }, data: { memoria: true }, width: 380, height: 520 },
      ];
      const lig = (a, b) => ({ id: rid('e'), source: a, target: b, type: 'atlas' });
      setNodes((ns) => ordenar([...ns.map((n) => ({ ...n, selected: false })), ...novos]));
      setEdges((es) => [...es, ...[tese, bib, vsl, yt].flatMap((x) => [lig(ag, x), lig(x, chat)])]);
      setTimeout(() => { try { rf.fitView({ nodes: novos.map((n) => ({ id: n.id })), padding: 0.15, duration: 300 }); } catch (_) {} }, 120);
    };
    // Bíblia da VSL nasce como um conjunto: Oferta → ChatGPT → (Bíblia da VSL, Inteligência em texto) → Chat sem histórico.
    // A Inteligência não vem ligada no chat: a VSL colada nela vira um arquivo embaixo, e é esse arquivo que se liga no chat (um por vez)
    const criarBiblia = (pos) => {
      const rid = (p) => p + Math.random().toString(36).slice(2, 9);
      const of = rid('ofe'), gpt = rid('cha'), bib = rid('bib'), txt = rid('int'), chat = rid('cha');
      const novos = [
        { id: of, type: 'oferta', position: { x: pos.x, y: pos.y + 250 }, data: {} },
        { id: gpt, type: 'chatgpt', position: { x: pos.x + 370, y: pos.y + 310 }, data: {} },
        { id: bib, type: 'biblia', position: { x: pos.x + 560, y: pos.y + 170 }, data: {} },
        { id: txt, type: 'inteligencia', position: { x: pos.x + 560, y: pos.y + 360 }, data: { texto: '', modo: 'vsl' } },
        { id: chat, type: 'chat', position: { x: pos.x + 960, y: pos.y }, data: { memoria: false }, width: 560, height: 700 },
      ];
      const lig = (a, b) => ({ id: rid('e'), source: a, target: b, type: 'atlas' });
      setNodes((ns) => ordenar([...ns.map((n) => ({ ...n, selected: false })), ...novos]));
      setEdges((es) => [...es, lig(of, gpt), lig(gpt, bib), lig(gpt, txt), lig(bib, chat)]);
      setTimeout(() => { try { rf.fitView({ nodes: novos.map((n) => ({ id: n.id })), padding: 0.15, duration: 300 }); } catch (_) {} }, 120);
    };
    // Em Criativos o Octopus Chat nasce como um conjunto: Oferta → ChatGPT → Chat. Todo anúncio é de uma oferta, então o nó Oferta já vem junto
    const criarChatCriativos = (pos) => {
      const rid = (p) => p + Math.random().toString(36).slice(2, 9);
      const of = rid('ofe'), gpt = rid('cha'), chat = rid('cha');
      const novos = [
        { id: of, type: 'oferta', position: { x: pos.x, y: pos.y + 120 }, data: {} },
        { id: gpt, type: 'chatgpt', position: { x: pos.x + 370, y: pos.y + 180 }, data: {} },
        { id: chat, type: 'chat', position: { x: pos.x + 560, y: pos.y }, data: { memoria: true }, width: 420, height: 560 },
      ];
      const lig = (a, b) => ({ id: rid('e'), source: a, target: b, type: 'atlas' });
      setNodes((ns) => ordenar([...ns.map((n) => ({ ...n, selected: false })), ...novos]));
      setEdges((es) => [...es, lig(of, gpt), lig(gpt, chat)]);
      setTimeout(() => { try { rf.fitView({ nodes: novos.map((n) => ({ id: n.id })), padding: 0.2, duration: 300 }); } catch (_) {} }, 120);
    };
    const criar = (tipo, pos) => {
      if (tipo === 'chat' && flow.area === 'criativos') return criarChatCriativos(pos);
      if (tipo === 'blocos') return criarBlocos(pos);
      if (tipo === 'biblia') return criarBiblia(pos);
      const novo = { id: tipo.slice(0, 3) + Math.random().toString(36).slice(2, 9), type: tipo, position: pos, data: dadosIniciais(tipo),
        ...(tipo === 'chat' ? { width: 380, height: 520 } : tipo === 'grupo' ? { width: 460, height: 320 } : {}) };
      setNodes((ns) => ordenar([...ns.map((n) => ({ ...n, selected: false })), { ...novo, selected: true }]));
      if (DENTRO[tipo]) setTimeout(() => encaixar(novo.id), 60);
    };
    // inteligência solta dentro de um grupo entra nele (e perde as ligações); arrastada para fora, sai
    const DENTRO = { inteligencia: true, arquivo: true, social: true };
    const encaixar = (nid) => {
      const n = rf.getNode(nid); if (!n || !DENTRO[n.type]) return;
      const pai = n.parentId ? rf.getNode(n.parentId) : null;
      const abs = pai ? { x: pai.position.x + n.position.x, y: pai.position.y + n.position.y } : n.position;
      const w = (n.measured && n.measured.width) || 280, h = (n.measured && n.measured.height) || 160;
      const cx = abs.x + w / 2, cy = abs.y + h / 2;
      const g = nRef.current.find((x) => x.type === 'grupo' && cx > x.position.x && cx < x.position.x + (x.measured?.width || x.width || 460) && cy > x.position.y && cy < x.position.y + (x.measured?.height || x.height || 320));
      if ((g && g.id) === n.parentId) return;
      // o grupo cresce para caber o nó inteiro (com folga)
      const rel = g ? { x: Math.max(16, abs.x - g.position.x), y: Math.max(64, abs.y - g.position.y) } : null;
      const gw = g ? Math.max(g.measured?.width || g.width || 460, rel.x + w + 24) : 0, gh = g ? Math.max(g.measured?.height || g.height || 320, rel.y + h + 24) : 0;
      setNodes((ns) => ordenar(ns.map((x) => (g && x.id === g.id ? { ...x, width: gw, height: gh }
        : x.id !== nid ? x : g
        ? { ...x, parentId: g.id, position: rel }
        : (({ parentId, ...resto }) => ({ ...resto, position: abs }))(x)))));
      if (g) {
        const tinha = eRef.current.some((e) => e.source === nid || e.target === nid);
        setEdges((es) => es.filter((e) => e.source !== nid && e.target !== nid));
        if (tinha) ctx.aviso('Dentro do grupo, a inteligência perde as ligações próprias: ligue o grupo.');
      }
      setTimeout(() => forcar && forcar(), 0);
    };
    // apagar um grupo solta o que estava dentro (não apaga as inteligências)
    const antesDeApagar = async ({ nodes: ns, edges: es }) => {
      if (ns.length && window.confirmarAcao) {              // excluir nó sempre pergunta (a conversa de um chat vai junto)
        const um = ns.length === 1, chat = ns.some((n) => n.type === 'chat');
        const ok = await window.confirmarAcao(um ? 'Tem certeza que deseja excluir este nó?' : `Tem certeza que deseja excluir ${ns.length} nós?`,
          chat ? 'A conversa do chat é apagada junto e não dá para recuperar.' : 'As ligações dele com os outros nós também saem.');
        if (!ok) return false;
      }
      const grupos = new Set(ns.filter((n) => n.type === 'grupo').map((n) => n.id));
      if (!grupos.size) return { nodes: ns, edges: es };
      const filhos = new Set(nRef.current.filter((x) => grupos.has(x.parentId)).map((x) => x.id));
      setNodes((all) => all.map((x) => { if (!grupos.has(x.parentId)) return x; const g = all.find((y) => y.id === x.parentId); const { parentId, ...resto } = x;
        return { ...resto, position: { x: g.position.x + x.position.x, y: g.position.y + x.position.y } }; }));
      return { nodes: ns.filter((n) => !filhos.has(n.id)), edges: es };
    };
    const soltar = (e) => {
      const arq = e.dataTransfer.getData('application/atlas-doc');
      if (arq) {                                              // arquivo arrastado da lista de um chat: vira uma cópia solta no flow
        e.preventDefault();
        let r = null; try { r = JSON.parse(arq); } catch (_) { return; }
        const a = ctx.arquivo(r.chat, r.ref); if (!a) return;
        const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
        const novo = { id: 'doc' + Math.random().toString(36).slice(2, 9), type: 'doc', position: { x: p.x - 150, y: p.y - 27 }, data: { nome: a.nome, texto: a.texto, md: !a.anexo, origem: r.chat, mini: true } };
        setNodes((ns) => ordenar([...ns.map((n) => ({ ...n, selected: false })), { ...novo, selected: true }]));
        return;
      }
      const tipo = e.dataTransfer.getData('application/atlas-no'); if (!tipo || !TIPOS[tipo]) return;
      if (tipo !== 'chatgpt' && tipo !== 'transcricao' && tipo !== 'biblia' && !(tipo === 'chat' && flow.area === 'criativos') && !nRef.current.some((n) => n.type === 'chatgpt')) return;
      e.preventDefault();
      const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
      criar(tipo, { x: p.x - 140, y: p.y - 40 });
    };
    const adicionar = (tipo) => {
      if (tipo !== 'chatgpt' && tipo !== 'transcricao' && tipo !== 'biblia' && !(tipo === 'chat' && flow.area === 'criativos') && !nRef.current.some((n) => n.type === 'chatgpt')) return;
      const el = document.querySelector('.react-flow');
      const r = el ? el.getBoundingClientRect() : { left: 0, top: 0, width: 800, height: 600 };
      const centro = rf.screenToFlowPosition({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
      // procura um lugar livre perto do centro da tela, em espiral
      const livre = (x, y) => !nRef.current.some((n) => Math.abs(n.position.x - x) < 320 && Math.abs(n.position.y - y) < 240);
      let pos = { x: centro.x - 140, y: centro.y - 90 };
      for (let i = 0; i < 40 && !livre(pos.x, pos.y); i++) {
        const ang = i * 0.9, raio = 160 + i * 40;
        pos = { x: centro.x - 140 + Math.cos(ang) * raio, y: centro.y - 90 + Math.sin(ang) * raio };
      }
      criar(tipo, pos);
    };

    // a visualização aberta de cada chat entra como nó derivado (não é salvo no flow e segue o chat)
    const arestas = [];
    const previas = nodes.filter((n) => n.type === 'chat' && n.data.previa != null).map((n) => {
      const w = (n.measured && n.measured.width) || n.width || 380, h = (n.measured && n.measured.height) || n.height || 520;
      const ph = 640;
      // a visualização abre EMBAIXO do chat, logo depois do painel "Arquivos" (a altura dele depende de quantas linhas de arquivos há)
      const ci = ctx.chat(n.id), msgs = ci.msgs, nArq = msgs.reduce((k, m) => k + (m.anexos || []).length + (m.doc && !m.stream ? 1 : 0), 0) + (ci.vslArq ? 1 : 0);
      const porLinha = Math.max(1, Math.floor((w - 24 + 6) / 176)), linhas = Math.ceil(nArq / porLinha);
      const gal = nArq ? 10 + 17 + 8 + Math.min(110, linhas * 32 + (linhas - 1) * 6) + 12 + 2 : 0;
      // tamanho já dado: o nó derivado não passa pela medição do React Flow (sem isso ele fica invisível para o mouse)
      return { id: 'pv-' + n.id, type: 'previa', position: { x: n.position.x, y: n.position.y + h + (gal ? 16 + gal : 0) + 18 }, zIndex: 4, data: { chat: n.id, i: n.data.previa, h: ph, ligada: edges.some((e) => e.source === 'pv-' + n.id) },
        width: 660, height: ph, measured: { width: 660, height: ph },
        draggable: false, selectable: true, connectable: true, deletable: false, focusable: false };
    });
    // etapas registradas no chat (✓ Etapa N · …): cartões à direita do chat; com o arquivo final pronto, viram um cartão só
    nodes.filter((n) => n.type === 'chat').forEach((n) => {
      const msgs = ctx.chat(n.id).msgs;
      let doc = -1; msgs.forEach((m, i) => { if (m.doc && !m.stream) doc = i; });
      let ets = etapasDoChat(msgs);
      if (doc >= 0 && msgs[doc].docTipo === 'briefing') {            // briefing pronto: as etapas vêm das seções do documento (a linha ✓ do chat, se houver, dá o resumo)
        const doDoc = etapasDoDoc(msgs[doc].doc);
        if (doDoc.length) ets = doDoc.map((e) => { const c = ets.find((x) => x.nome.toLowerCase() === e.nome.toLowerCase()); return c ? { ...e, escolha: c.escolha } : e; });
      }
      if (!ets.length) {                                              // chat do Blocos de VSL: cada bloco escrito vira um cartão ao lado, na ordem da VSL (a versão mais nova de cada bloco)
        const blocos = new Map();
        msgs.forEach((m) => { if (!m.doc || m.stream || m.docTipo !== 'bloco') return;
          const campo = (k) => ((String(m.doc).match(new RegExp('^' + k + ':\\s*"?([^"\\n]*)"?\\s*$', 'm')) || [])[1] || '').trim();
          const nome = campo('bloco') || 'Bloco', corpo = String(m.doc).replace(/^---[\s\S]*?\n---\n?/, '').trim();
          blocos.set(nome.toLowerCase(), { ordem: +campo('ordem') || 0, nome, detalhe: corpo, escolha: corpo.length.toLocaleString('pt-BR') + ' caracteres' + (campo('tempo') ? ' · ' + campo('tempo') : '') }); });
        ets = [...blocos.values()].sort((a, b) => (a.ordem || 99) - (b.ordem || 99)).map((b, k) => ({ ...b, n: k + 1 }));
      }
      if (!ets.length) return;
      const w = (n.measured && n.measured.width) || n.width || 380;
      const x0 = n.position.x + w + 72;
      // arrastar e redimensionar: o lugar e o tamanho de cada cartão ficam guardados no nó do chat (relativos a ele).
      // Abrir um cartão não empurra os outros: ele abre por cima. Quem foi mexido por último fica na frente
      const livre = { draggable: true, selectable: true, connectable: false, deletable: false, focusable: false };
      const guard = n.data.etapasPos || {}, abertas = n.data.etapasAbertas || [], ordem = n.data.etapasOrdem || [];
      ets.forEach((e, k) => { const aberta = abertas.includes(e.n), p = guard['p' + e.n], t = guard[(aberta ? 'a' : 'm') + e.n] || {};
        const w2 = t.w || (aberta ? 460 : 300), h2 = aberta ? (t.h || 380) : 58, id2 = 'et-' + n.id + '-' + e.n;
        previas.push({ id: id2, type: 'etapa', position: p ? { x: n.position.x + p.dx, y: n.position.y + p.dy } : { x: x0, y: n.position.y + k * 72 },
          width: w2, height: h2, measured: { width: w2, height: h2 }, zIndex: 10 + (ordem.indexOf(e.n) + 1) + (aberta && !ordem.includes(e.n) ? 1 : 0), ...livre, data: { ...e, chat: n.id, aberta } });
        arestas.push({ id: 'ee-' + id2, source: n.id, sourceHandle: 'et', target: id2, type: 'fixa', className: 'aedge', selectable: false, deletable: false, focusable: false }); });
    });
    const derivado = (x) => /^(pv|tr|et|eg)-/.test(String(x || ''));
    // cartão de etapa arrastado ou redimensionado: guarda no nó do chat (o cartão em si não é salvo)
    const mudarNos = useCallback((ch) => {
      const meus = ch.filter((c) => /^et-/.test(String(c.id || '')) && ((c.type === 'position' && c.position) || (c.type === 'dimensions' && c.dimensions && c.resizing !== undefined)));
      if (meus.length) setNodes((ns) => { let out = ns;
        for (const c of meus) { const m = String(c.id).match(/^et-(.+)-(\d+)$/); if (!m) continue;
          out = out.map((x) => { if (x.id !== m[1]) return x;
            const aberta = (x.data.etapasAbertas || []).includes(+m[2]);
            const chave = c.type === 'position' ? 'p' + m[2] : (aberta ? 'a' : 'm') + m[2];
            const g = c.type === 'position' ? { dx: c.position.x - x.position.x, dy: c.position.y - x.position.y } : { w: Math.round(c.dimensions.width), h: Math.round(c.dimensions.height) };
            return { ...x, data: { ...x.data, etapasPos: { ...(x.data.etapasPos || {}), [chave]: g } } }; }); }
        return out; });
      onNodesChange(ch.filter((c) => !derivado(c.id)));
    }, [onNodesChange]);
    return html`<${ReactFlow} nodes=${previas.length ? nodes.concat(previas) : nodes} edges=${arestas.length ? edges.concat(arestas) : edges} nodeTypes=${nodeTypes} edgeTypes=${edgeTypes}
        onNodesChange=${mudarNos} onEdgesChange=${onEdgesChange} onConnect=${onConnect} isValidConnection=${valida} onNodeDragStop=${(e, n) => encaixar(n.id)} onBeforeDelete=${antesDeApagar} onNodesDelete=${(ns) => { ns.forEach((n) => ctx.excluirNo(n.id)); const fora = new Set(ns.flatMap((n) => ['pv-' + n.id, 'tr-' + n.id])); setEdges((es) => es.filter((e) => !fora.has(e.source))); }}
        defaultViewport=${flow.viewport || { x: 0, y: 0, zoom: 1 }} fitView=${!flow.viewport} fitViewOptions=${{ padding: 0.3 }}
        onMoveEnd=${(e, vp) => { flow.viewport = vp; ctx.salvar(); }}
        minZoom=${0.2} maxZoom=${2.5} deleteKeyCode=${['Backspace', 'Delete']} proOptions=${{ hideAttribution: true }}
        defaultEdgeOptions=${{ className: 'aedge' }} colorMode="dark"
        selectionOnDrag=${sel} panOnDrag=${sel ? [1, 2] : true} selectionMode="partial" className=${sel ? 'modo-selecao' : ''}
        onSelectionDragStop=${(e, ns) => (ns || []).forEach((n) => encaixar(n.id))}
        onDragOver=${(e) => { const ts = [...e.dataTransfer.types]; if (ts.includes('application/atlas-no')) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } else if (ts.includes('application/atlas-doc')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } }} onDrop=${soltar}>
      <${Background} variant=${BackgroundVariant.Dots} gap=${22} size=${1.5} />
      ${nodes.some((n) => n.type === 'chatgpt') ? null : html`<div class="fvazio"><b>${nodes.length ? 'Falta a IA do flow' : 'Comece pelo ChatGPT'}</b><span>Arraste o ChatGPT da barra para o canvas. Ele é a IA que faz o flow funcionar; os outros nós vêm depois dele.</span></div>`}
      <${Barra} adicionar=${adicionar} temIA=${nodes.some((n) => n.type === 'chatgpt')} area=${flow.area} sel=${sel} setSel=${setSel}
        marcados=${nodes.filter((n) => n.selected).length} excluirMarcados=${() => rf.deleteElements({ nodes: nodes.filter((n) => n.selected).map((n) => ({ id: n.id })) })} />
    <//>`;
  }

  let raiz = null;
  window.AtlasFlow = {
    mount(el, flow, callbacks) {
      ctx = callbacks;
      raiz = ReactDOM.createRoot(el);
      raiz.render(html`<${ReactFlowProvider}><${Canvas} flow=${flow} /><//>`);
    },
    unmount() { if (raiz) { raiz.unmount(); raiz = null; } ctx = null; api = null; },
    refresh() { forcar && forcar(); },
    ligacoes() { return api ? api.ligacoes() : { nodes: [], edges: [] }; },
    enquadrar() { api && api.enquadrar(); },
    focar(id) { api && api.focar(id); },
    patch(id, p) { api && api.patch(id, p); },
    vslDoChat(chatId, idVsl, texto) { api && api.vslDoChat(chatId, idVsl, texto); },
    nos() { return api ? api.ligacoes().nodes : []; },
    TIPOS,
  };
})();
