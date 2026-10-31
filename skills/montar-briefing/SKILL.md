---
name: montar-briefing
description: Monta o Briefing de tese de uma oferta em qualquer chat, em conversa, uma etapa por vez, a partir das bíblias, e no fim entrega o documento no formato do modelo. Só roda quando o usuário invoca com #montar-briefing ou quando o pedido dele é montar o briefing ou a tese de uma oferta.
barra: true
prefixo: "#"
tipo: funcao
agentes: []
categoria: VSL
usa: [briefing-de-tese]
biblioteca: [Modelos/Briefing de tese]
resumo: Define a tese da oferta com você, etapa por etapa, partindo das bíblias, e entrega o briefing no formato do modelo
---

# Montar briefing de tese

Esta função monta o briefing de tese de **uma oferta**, etapa por etapa, dentro de qualquer chat. As etapas, a ordem e o jeito de conduzir cada uma são os do manual do Briefing da tese, que vem logo abaixo. O formato é o do modelo `Biblioteca/Modelos/Briefing de tese`, que também vem abaixo. Aqui está só o que muda por ser uma função.

## Antes de começar

1. **Qual oferta.** Com o nó Oferta ligado, é a dele. Sem nó, pergunte o expert e a oferta, mostrando os que existem (`listar_cofre`). A oferta pode ser nova.
2. **As bíblias.** O briefing parte das bíblias. Use `listar_biblias` e `ler_biblia`; bíblia que veio ligada no flow ou anexada no chat também vale. Se não houver nenhuma, diga isso e ofereça montar uma primeiro com a função de montar a bíblia da VSL. Não invente o que o nicho faz.
3. **O expert.** Se o expert já existe, leia as notas `Projetos/{Expert}/Credenciais.md` e `Projetos/{Expert}/História.md` (`ler_nota`) e use o que estiver lá na etapa da narrativa da VSL, em vez de perguntar de novo.

## Etapa por etapa

- Uma etapa por mensagem, na ordem do manual. Em cada uma: o que as bíblias mostram, a sua sugestão e a pergunta ao usuário.
- Só avance quando ele escolher ou aprovar. Guarde as escolhas e não as mude depois sem ele pedir.
- No começo de cada etapa, diga em qual está: `Etapa N de T: nome`.
- Se ele pedir "faça tudo com as suas sugestões", siga até o fim usando a sugestão de cada etapa e avise que foi assim.

## No fim

Você não escreve o documento final: o arquivo do briefing é montado pelo Octopus IA com as seções que você registrou em cada etapa (veja "O registro da etapa" no manual). Com a última etapa registrada, diga em uma linha que o briefing está completo e pergunte se o usuário quer guardar no Cérebro; se quiser, grave com `salvar_no_cerebro` na oferta combinada.

## Regras

- O que vem das bíblias é citado como vindo delas. Sugestão sua é dita como sugestão.
- Sem julgamento e sem ressalva sobre prova ou ciência. O que você propôs e o expert não confirmou leva a marca `[confirmar]`.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
