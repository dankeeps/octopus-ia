/* Grafo do Cérebro (menu lateral › Cérebro): todas as notas do Octopus IA e as ligações entre elas, em 3D.
   Os pontos formam a silhueta de um cérebro: cada área (narrativas, formatos, ângulos…) ocupa uma região dele, e os
   pontos ficam se mexendo de leve. Tudo cinza; o ponto sob o mouse, as ligações e os vizinhos dele ficam roxos.
   Usa o three.js de /vendor (sem rede). */
(function () {
  let atual = null;
  const ROXO = 0xb5ff00,      /* o destaque ao passar o mouse: o verde do Octopus (o nome ficou de quando era roxo) */
     CINZA = 0x9a9aa2;

  // direção (unitária) → ponto na superfície de um cérebro: dois hemisférios, fenda no meio, base achatada, cerebelo atrás
  function cerebro(dx, dy, dz) {
    let x = dx * 1.22, y = dy * 1.0, z = dz * 1.5;
    const sulcos = 1 + 0.045 * Math.sin(dx * 9 + dz * 7) * Math.cos(dy * 8 + dz * 5);       // as dobras
    x *= sulcos; y *= sulcos; z *= sulcos;
    const meio = Math.exp(-(dx * dx) / 0.02);                 // a fenda entre os hemisférios
    if (dy > -0.1) y -= meio * 0.2;
    x += Math.sign(dx || 1) * 0.07;
    if (y < 0) y *= 0.62;                                     // base achatada
    if (dy < -0.15 && dz < -0.35) { y -= 0.26; z += 0.12; x *= 0.78; }      // cerebelo
    else if (dy < 0.05 && Math.abs(dz) < 0.55 && Math.abs(dx) > 0.45) { y -= 0.16 * (1 - Math.abs(dz) / 0.55); x *= 1.05; }      // lobo temporal, a barriga de baixo dos lados
    y += 0.12 * Math.max(0, dz) * (dy > 0 ? 1 : 0.2);         // testa um pouco mais alta
    return [x, y, z];
  }
  // onde fica o centro de cada área, como direção
  const REGIAO = { narrativas: [-0.55, 0.55, 0.6], formatos: [0.55, 0.55, 0.6], angulos: [-0.7, 0.45, -0.45], modelos: [0.2, -0.6, -0.75],
    regras: [0.0, -0.75, 0.2], ofertas: [0.7, 0.1, 0.0], auditoria: [0.7, 0.45, -0.5], spy: [-0.75, -0.2, 0.25] };
  const norm = (v) => { const m = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / m, v[1] / m, v[2] / m]; };

  function montar(el, dados, aoAbrir) {
    desmontar();
    const T = window.THREE;
    if (!T || !el || !dados) return null;
    const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    el.appendChild(renderer.domElement);
    const cena = new T.Scene(), cam = new T.PerspectiveCamera(36, 1, 0.1, 100);
    let dist = 4.7; cam.position.set(0, 0, dist);
    const grupo = new T.Group(); cena.add(grupo);

    // ---- nós: cada um ganha um lugar na superfície do cérebro, perto do centro da área dele ----
    const ids = new Map(), nos = dados.nos.filter((n) => n.g !== 'centro').map((n, i) => ({ ...n, i, viz: [], fase: Math.random() * 6.28, amp: 0.012 + Math.random() * 0.022 }));
    nos.forEach((n) => ids.set(n.id, n));
    const lig = dados.ligacoes.map((l) => ({ a: ids.get(l.a), b: ids.get(l.b), t: l.t })).filter((l) => l.a && l.b);
    lig.forEach((l) => { l.a.viz.push(l.b); l.b.viz.push(l.a); });
    const folhas = nos.filter((n) => n.nivel === 3);
    // pontos espalhados por igual na esfera (espiral de Fibonacci), com sobra para o encaixe ficar natural
    const M = Math.ceil(folhas.length * 1.25) + 20, livres = [];
    for (let k = 0; k < M; k++) { const yy = 1 - (2 * (k + 0.5)) / M, r = Math.sqrt(1 - yy * yy), a = k * 2.399963; livres.push([Math.cos(a) * r, yy, Math.sin(a) * r]); }
    const porArea = {}; folhas.forEach((n) => (porArea[n.g] = porArea[n.g] || []).push(n));
    Object.keys(porArea).sort((a, b) => porArea[b].length - porArea[a].length).forEach((g) => {
      const c = norm(REGIAO[g] || [0, 1, 0]);
      livres.sort((p, q) => (q[0] * c[0] + q[1] * c[1] + q[2] * c[2]) - (p[0] * c[0] + p[1] * c[1] + p[2] * c[2]));
      porArea[g].forEach((n) => { const d = livres.shift(); n.dir = d; const p = cerebro(d[0], d[1], d[2]); const f = 0.94 + Math.random() * 0.08; n.base = [p[0] * f, p[1] * f, p[2] * f]; });
    });
    // os nós de área e de subgrupo ficam por dentro: é deles que saem os "fios"
    nos.filter((n) => n.nivel < 3).forEach((n) => {
      const filhos = n.viz.filter((x) => x.base);
      if (filhos.length) { const m = [0, 0, 0]; filhos.forEach((f) => { m[0] += f.base[0]; m[1] += f.base[1]; m[2] += f.base[2]; }); const k = (n.nivel === 1 ? 0.3 : 0.62) / filhos.length; n.base = [m[0] * k, m[1] * k, m[2] * k]; }
      else { const c = norm(REGIAO[n.g] || [0, 1, 0]), p = cerebro(c[0], c[1], c[2]), k = n.nivel === 1 ? 0.3 : 0.62; n.base = [p[0] * k, p[1] * k, p[2] * k]; }
    });
    nos.filter((n) => n.nivel === 1).forEach((n) => {          // a área fica no meio dos subgrupos dela, quando tem
      const subs = n.viz.filter((x) => x.nivel === 2); if (!subs.length) return;
      const m = [0, 0, 0]; subs.forEach((f) => { m[0] += f.base[0]; m[1] += f.base[1]; m[2] += f.base[2]; }); n.base = [m[0] * 0.5 / subs.length, m[1] * 0.5 / subs.length, m[2] * 0.5 / subs.length];
    });

    // ---- pontos ----
    const N = nos.length, pos = new Float32Array(N * 3), cor = new Float32Array(N * 3), tam = new Float32Array(N);
    const gp = new T.BufferGeometry();
    gp.setAttribute('position', new T.BufferAttribute(pos, 3)); gp.setAttribute('color', new T.BufferAttribute(cor, 3)); gp.setAttribute('tam', new T.BufferAttribute(tam, 1));
    const mp = new T.ShaderMaterial({ transparent: true, depthWrite: false, vertexColors: true,
      uniforms: { escala: { value: 1 }, perto: { value: 3.4 } },
      vertexShader: 'attribute float tam; varying vec3 vCor; varying float vProf; uniform float escala; uniform float perto; void main(){ vCor=color; vec4 mv=modelViewMatrix*vec4(position,1.0); vProf=clamp((-mv.z-perto)/2.3,0.0,1.0); gl_PointSize=tam*escala*(7.0/-mv.z); gl_Position=projectionMatrix*mv; }',
      fragmentShader: 'varying vec3 vCor; varying float vProf; void main(){ float d=length(gl_PointCoord-0.5); if(d>0.5) discard; float a=smoothstep(0.5,0.32,d)*(1.0-vProf*0.93); gl_FragColor=vec4(vCor,a); }' });
    const pontos = new T.Points(gp, mp); grupo.add(pontos);
    // ---- poeira: pontinhos miúdos que desenham a silhueta do cérebro (não são notas, não têm clique) ----
    // Os sulcos (as dobras) são faixas sem pontinho: é o que faz a forma ler como cérebro e não como uma bola
    const sulco = (x, y, z) => Math.sin(x * 6.5 + Math.sin(z * 5.2) * 2.4 + y * 2.0) * Math.cos(y * 6.2 + Math.sin(x * 4.6) * 2.2 + z * 3.4);
    const lista = [];
    for (let k = 0; k < 5200; k++) {
      const yy = 1 - (2 * (k + 0.5)) / 5200, r = Math.sqrt(1 - yy * yy), a = k * 2.399963, dx = Math.cos(a) * r, dz = Math.sin(a) * r;
      const cerebelo = yy < -0.15 && dz < -0.35;
      if (!cerebelo && Math.abs(dx) < 0.07 && yy > -0.2) continue;                         // a fenda entre os hemisférios
      if (!cerebelo && Math.abs(sulco(dx, yy, dz)) < 0.2) continue;                        // os sulcos
      if (cerebelo && Math.abs(Math.sin(yy * 46)) < 0.42) continue;                        // cerebelo: listras finas
      if (yy < -0.72 && !cerebelo) continue;                                               // a base fica aberta
      const p = cerebro(dx, yy, dz), f = 0.985 + Math.random() * 0.03;
      lista.push(p[0] * f, p[1] * f, p[2] * f);
    }
    for (let k = 0; k < 90; k++) { const a = Math.random() * 6.28, h = Math.random(); lista.push(Math.cos(a) * 0.16 * (1 - h * 0.3), -0.62 - h * 0.55, -0.35 + Math.sin(a) * 0.16 - h * 0.12); }   // o tronco
    const P = lista.length / 3, ppos = new Float32Array(lista), pcor = new Float32Array(P * 3), ptam = new Float32Array(P);
    for (let k = 0; k < P; k++) { const luz = 0.22 + Math.random() * 0.2; pcor[k * 3] = pcor[k * 3 + 1] = luz * 0.6; pcor[k * 3 + 2] = luz * 0.64; ptam[k] = 1.5 + Math.random() * 1.1; }
    const gd = new T.BufferGeometry(); gd.setAttribute('position', new T.BufferAttribute(ppos, 3)); gd.setAttribute('color', new T.BufferAttribute(pcor, 3)); gd.setAttribute('tam', new T.BufferAttribute(ptam, 1));
    const poeira = new T.Points(gd, mp); grupo.add(poeira);
    // ---- ligações ----
    const lpos = new Float32Array(lig.length * 6), lcor = new Float32Array(lig.length * 6);
    const gl2 = new T.BufferGeometry(); gl2.setAttribute('position', new T.BufferAttribute(lpos, 3)); gl2.setAttribute('color', new T.BufferAttribute(lcor, 3));
    const linhas = new T.LineSegments(gl2, new T.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, depthWrite: false, blending: T.AdditiveBlending }));
    grupo.add(linhas);

    // ---- nomes: os das áreas sempre; o do ponto em foco e dos vizinhos ----
    const rotulos = document.createElement('div'); rotulos.className = 'gf-rotulos'; el.appendChild(rotulos);
    const etiqueta = (n, cls) => { const d = document.createElement('span'); d.className = 'gf-rot ' + cls; d.textContent = n.nome.length > 38 ? n.nome.slice(0, 37) + '…' : n.nome; d.style.opacity = 0; rotulos.appendChild(d); return d; };
    nos.filter((n) => n.nivel === 1).forEach((n) => { n.rot = etiqueta(n, 'area'); const c = norm(REGIAO[n.g] || [0, 1, 0]), p = cerebro(c[0], c[1], c[2]); n.rotulo = [p[0] * 1.16, p[1] * 1.16, p[2] * 1.16]; n.base = n.rotulo; n.amp = 0.008;
      n.rot.addEventListener('click', () => { sel = sel === n ? null : n; }); n.rot.addEventListener('mouseenter', () => { sobre = n; }); n.rot.addEventListener('mouseleave', () => { sobre = null; }); });
    const foco = document.createElement('span'); foco.className = 'gf-rot foco'; foco.style.opacity = 0; rotulos.appendChild(foco);      // nasce invisível: sem isso piscava no canto antes do primeiro quadro
    const extras = []; for (let k = 0; k < 14; k++) { const d = document.createElement('span'); d.className = 'gf-rot viz'; d.style.opacity = 0; rotulos.appendChild(d); extras.push(d); }

    let W = 1, H = 1, rx = 0.32, ry = -0.95, sobre = null, sel = null, busca = '', escondidos = new Set(), arr = null, mexeu = false, vivo = true, parado = 0;
    function tamanho() { W = el.clientWidth || 800; H = el.clientHeight || 600; renderer.setSize(W, H, false); cam.aspect = W / H; cam.updateProjectionMatrix(); mp.uniforms.escala.value = Math.min(1.5, H / 620) * renderer.getPixelRatio(); }
    const ro = new ResizeObserver(tamanho); ro.observe(el); tamanho();

    const raio = new T.Raycaster(), ponteiro = new T.Vector2(), v = new T.Vector3();
    function acha(e) {
      // a tela do app tem zoom de 90%: a posição do mouse precisa ser convertida para a medida do desenho
      const r = renderer.domElement.getBoundingClientRect(), px = (e.clientX - r.left) * (W / r.width), py = (e.clientY - r.top) * (H / r.height);
      let melhor = null, md = 1e9;
      for (const n of nos) { if (escondidos.has(n.g) || n.atras) continue; const d = Math.hypot(n.sx - px, n.sy - py), alcance = n.nivel === 1 ? 20 : n.nivel === 2 ? 14 : 12; if (d < alcance && d - alcance < md) { md = d - alcance; melhor = n; } }
      return melhor;
    }
    const cv = renderer.domElement;
    cv.addEventListener('pointerdown', (e) => { arr = { x: e.clientX, y: e.clientY }; mexeu = false; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener('pointermove', (e) => {
      if (arr) { const dx = e.clientX - arr.x, dy = e.clientY - arr.y; if (Math.abs(dx) + Math.abs(dy) > 3) mexeu = true; ry += dx * 0.006; rx = Math.max(-1.3, Math.min(1.3, rx + dy * 0.006)); arr = { x: e.clientX, y: e.clientY }; parado = 240; return; }
      sobre = acha(e); cv.style.cursor = sobre ? 'pointer' : 'grab';
    });
    cv.addEventListener('pointerup', (e) => { if (!mexeu) { const n = acha(e); sel = n && n === sel && n.nivel !== 3 ? null : n; if (n && n.nivel === 3) aoAbrir && aoAbrir(n.id); } arr = null; });
    cv.addEventListener('pointerleave', () => { sobre = null; });
    cv.addEventListener('wheel', (e) => { e.preventDefault(); dist = Math.max(2.6, Math.min(12, dist * Math.exp(e.deltaY * 0.0012))); }, { passive: false });

    const cz = new T.Color(CINZA), rxo = new T.Color(ROXO);
    const t0 = performance.now();
    function quadro() {
      if (!vivo) return;
      const t = (performance.now() - t0) / 1000;
      if (parado > 0) parado--; else if (!sobre && !arr) ry += 0.0011;
      grupo.rotation.set(rx, ry, 0); grupo.scale.setScalar(1 + Math.sin(t * 0.8) * 0.012);
      cam.position.z += (dist - cam.position.z) * 0.12; mp.uniforms.perto.value = cam.position.z - 1.15;
      const alvo = sobre || sel, q = busca.trim().toLowerCase();
      let viz = null;                                          // área selecionada acende a área inteira; subgrupo acende as notas dele
      if (alvo) { viz = new Set([alvo, ...alvo.viz]); if (alvo.nivel === 1) for (const n of nos) { if (n.g === alvo.g) viz.add(n); } }
      const pulso = 1;                                         // a respiração do cérebro é na escala do grupo
      for (const n of nos) {
        const b = n.base, k = n.i * 3, a = n.amp;
        n.x = (b[0] + Math.sin(t * 0.7 + n.fase) * a) * pulso; n.y = (b[1] + Math.cos(t * 0.6 + n.fase * 1.3) * a) * pulso; n.z = (b[2] + Math.sin(t * 0.5 + n.fase * 0.7) * a) * pulso;
        pos[k] = n.x; pos[k + 1] = n.y; pos[k + 2] = n.z;
        const fora = escondidos.has(n.g), acesa = (viz && viz.has(n)) || (q && n.nome.toLowerCase().includes(q));
        const c = acesa ? rxo : cz, luz = fora ? 0 : acesa ? 1 : (viz || q) ? 0.28 : n.nivel === 1 ? 1 : n.nivel === 3 ? 0.78 : 0.5;
        cor[k] = c.r * luz; cor[k + 1] = c.g * luz; cor[k + 2] = c.b * luz;
        tam[n.i] = fora ? 0 : n.nivel === 1 ? 9 : n.nivel === 2 ? 6.5 : 5.5;      // tamanho fixo: selecionar só muda a cor
      }
      gp.attributes.position.needsUpdate = true; gp.attributes.color.needsUpdate = true; gp.attributes.tam.needsUpdate = true;
      for (let i = 0; i < lig.length; i++) {
        const l = lig[i], k = i * 6, liga = alvo && (l.a === alvo || l.b === alvo || (alvo.nivel === 1 && l.t === 'braco' && l.a.g === alvo.g && l.b.g === alvo.g)), fora = escondidos.has(l.a.g) || escondidos.has(l.b.g);
        lpos[k] = l.a.x; lpos[k + 1] = l.a.y; lpos[k + 2] = l.a.z; lpos[k + 3] = l.b.x; lpos[k + 4] = l.b.y; lpos[k + 5] = l.b.z;
        const c = liga ? rxo : cz, luz = fora ? 0 : liga ? 0.95 : (alvo || q) ? 0.04 : l.t === 'link' ? 0.2 : 0.13;
        for (let j = 0; j < 6; j += 3) { lcor[k + j] = c.r * luz; lcor[k + j + 1] = c.g * luz; lcor[k + j + 2] = c.b * luz; }
      }
      gl2.attributes.position.needsUpdate = true; gl2.attributes.color.needsUpdate = true;
      grupo.updateMatrixWorld(); cam.updateMatrixWorld();
      for (const n of nos) { v.set(n.x, n.y, n.z).applyMatrix4(grupo.matrixWorld); n.atras = v.z < -0.25; v.project(cam); n.sx = (v.x * 0.5 + 0.5) * W; n.sy = (-v.y * 0.5 + 0.5) * H;
        if (n.rotulo) { n.ratras = n.atras; n.rsx = n.sx; n.rsy = n.sy - 17; } }
      const poe = (d, n, dy) => { d.style.transform = `translate(-50%,-50%) translate(${n.sx}px,${n.sy + dy}px)`; };
      nos.forEach((n) => { if (!n.rot) return; n.rot.style.transform = `translate(-50%,-50%) translate(${n.rsx}px,${n.rsy}px)`; n.rot.style.opacity = escondidos.has(n.g) ? 0 : n.ratras ? 0 : (alvo && !viz.has(n)) ? 0.25 : 0.9; n.rot.style.pointerEvents = n.ratras || escondidos.has(n.g) ? 'none' : 'auto'; n.rot.classList.toggle('on', !!viz && viz.has(n)); });
      if (alvo && alvo.nivel !== 1) { foco.textContent = alvo.nome; foco.style.opacity = 1; poe(foco, alvo, -18); } else foco.style.opacity = 0;
      const vz = alvo ? alvo.viz.filter((x) => x.nivel !== 1 && !x.atras).slice(0, extras.length) : [];
      extras.forEach((d, k) => { const n = vz[k]; if (!n) { d.style.opacity = 0; return; } d.textContent = n.nome.length > 30 ? n.nome.slice(0, 29) + '…' : n.nome; d.style.opacity = 0.85; poe(d, n, 13); });
      renderer.render(cena, cam);
      atual.raf = requestAnimationFrame(quadro);
    }
    atual = {
      raf: 0, el,
      parar() { vivo = false; cancelAnimationFrame(this.raf); ro.disconnect(); renderer.dispose(); el.innerHTML = ''; },
      buscar(q) { busca = q || ''; },
      esconder(g, sim) { if (sim) escondidos.add(g); else escondidos.delete(g); },
      escondidos: () => escondidos,
      selecionar(id) { sel = ids.get(id) || null; },
      enquadrar() { rx = 0.32; ry = -0.95; dist = 4.7; },
    };
    quadro();
    return atual;
  }
  function desmontar() { if (atual) { atual.parar(); atual = null; } }
  window.AtlasGrafo = { montar, desmontar, atual: () => atual, cores: {} };
})();
