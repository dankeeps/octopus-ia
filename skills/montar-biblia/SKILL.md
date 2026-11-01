---
name: montar-biblia
description: Monta a Bíblia de uma VSL em qualquer chat, uma seção por vez, no formato do modelo, e no fim entrega o documento completo. Só roda quando o usuário invoca com #montar-biblia ou quando o pedido dele é montar a bíblia de uma VSL.
barra: true
prefixo: "#"
tipo: funcao
agentes: []
categoria: VSL
usa: [biblia-do-nicho]
biblioteca: [Modelos/Bíblia do nicho]
resumo: Estuda uma VSL e monta a bíblia dela etapa por etapa, uma seção de cada vez, no formato do modelo
---

# Montar bíblia da VSL

Esta função monta a bíblia de **uma VSL**, etapa por etapa, dentro de qualquer chat. As regras de conteúdo de cada seção são as do manual da Bíblia do nicho, que vem logo abaixo. O formato é o do modelo `Biblioteca/Modelos/Bíblia do nicho`, que também vem abaixo. Aqui está só o jeito de conduzir.

## De onde vem a VSL

A VSL pode estar: colada ou anexada neste chat, ligada no flow (uma transcrição, uma inteligência em texto ou em arquivo) ou guardada no Cérebro (a VSL de uma oferta). Se o usuário disser o nome e ela estiver no Cérebro, ache com `listar_notas` e leia com `ler_nota`. Se não chegou nenhuma VSL, peça e pare. É uma VSL por bíblia: se houver mais de uma, pergunte por qual começar.

## Etapa por etapa

A bíblia tem as seções do modelo, na ordem dele. Você entrega **uma seção por mensagem**:

1. Na primeira mensagem, diga em uma linha qual VSL vai estudar e quantas etapas são, e já entregue a etapa 1.
2. Cada etapa é a seção inteira, do título `## N. nome` até o fim dela, no formato exato do modelo (mesmos títulos, mesmas tabelas, mesmas colunas).
3. Na etapa da estrutura, divida a VSL em blocos e meça com a ferramenta `medir_blocos` (passe `anexo` com o nome do arquivo, ou `texto` com a VSL quando ela veio colada ou ligada no flow). Não estime tempo de cabeça.
4. Termine cada etapa com uma linha só: `Etapa N de T pronta. Posso seguir para a etapa N+1 (nome)?`
5. Se o usuário pedir ajuste, refaça só aquela seção. Se disser para seguir, vá para a próxima. Se ele pedir "faça tudo de uma vez", entregue as que faltam em sequência, sem parar.

Ignore, do manual abaixo, o "Modo por partes" (é de outro lugar do Octopus IA) e a regra de não parar para confirmar: aqui você para ao fim de cada etapa.

## No fim

Depois da última etapa aprovada, entregue a **bíblia completa**: a resposta é só o documento em Markdown, começando pela linha `---` do cabeçalho do modelo (`tipo`, `nicho`, `expert`, `oferta`, `vsl`, `estrutura`, `duracao`, `criada`), com todas as seções já ajustadas, sem texto antes nem depois. É isso que faz o arquivo aparecer no chat.

Na mensagem seguinte, ou se o usuário já tiver pedido, pergunte em uma linha se ele quer guardar no Cérebro e em qual oferta, e grave com `salvar_no_cerebro`.

## Regras

- Tudo sai da VSL. O que ela não mostra fica vazio ou com "(a VSL não mostra)".
- O núcleo de conversão é uma frase só, com a principal dor e como ela se resolve.
- Em dores, desejos, promessas, soluções comuns, crenças e objeções, só trechos copiados da VSL, sem repetir o mesmo item.
- Não mude o texto da VSL e não a reescreva na resposta.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
