---
name: dividir-vsl
description: Divide uma VSL em blocos sem reescrever o texto. Serve para a VSL da oferta que já está no Cérebro (os títulos dos blocos entram na nota dela) e para uma VSL de referência que o usuário mandou no chat, como a de um concorrente (fica guardada, dividida, na pasta VSL/Referências da oferta). Só roda quando o usuário invoca com #dividir-vsl no chat.
barra: true
prefixo: "#"
tipo: funcao
agentes: []
categoria: VSL
resumo: Divide uma VSL em blocos, pondo o título de cada bloco no ponto certo do texto, sem mudar nenhuma palavra
---

# Dividir VSL em blocos

Esta função marca onde cada bloco de uma VSL começa. O texto não é reescrito: você diz o nome de cada bloco e as primeiras palavras dele, e o Octopus IA põe o título no ponto certo, com a ferramenta `dividir_vsl`.

## Qual VSL

Há dois casos, e a ferramenta atende os dois:

1. **A VSL da oferta, que já está no Cérebro** (`Projetos/{Expert}/{Oferta}/VSL/VSL V1.md`, V2…). Informe `caminho`. Os títulos entram na própria nota, na seção Script. Se ela já tinha blocos, a divisão nova substitui a antiga.
2. **Uma VSL que o usuário mandou no chat** (colada ou anexada). Informe `anexo`. O próprio arquivo do chat é editado: ganha os títulos dos blocos, e o usuário abre o arquivo e já vê a VSL dividida. Se ele também quiser guardar essa VSL como referência (a de um concorrente, por exemplo), informe além disso `expert`, `oferta` e um `nome`: uma cópia vai para `Projetos/{Expert}/{Oferta}/VSL/Referências/`. A VSL da própria oferta não é guardada como referência: para ela, use `#salvar-vsl`.

Se não estiver claro qual é o caso, ou de qual oferta se trata, pergunte. Com o nó Oferta ligado, a oferta é a dele. Para achar a nota da VSL, use `listar_notas` na pasta VSL da oferta.

## Como dividir

1. **Leia a VSL inteira** antes de marcar qualquer coisa (`ler_nota`, ou o texto que chegou na conversa).
2. **Se o texto já veio com blocos marcados** (títulos, numeração), use essa divisão e esses nomes.
3. **Se veio corrido, divida você.** Um bloco é um trecho grande com uma função só. Os mais comuns: abrir e prender (lead), contar quem é (background), a história emocional, a história da descoberta, o mecanismo do problema, o mecanismo da solução, a apresentação do produto, as provas, a oferta, os bônus, a garantia, o fechamento. Use os nomes da biblioteca de estruturas de VSL (`Biblioteca/Estruturas de VSL`) quando o bloco for um dos que já têm nome; se não for, dê um nome curto que diga o que ele faz.
4. **Use quantos blocos a VSL tiver.** Não force uma quantidade e não quebre um bloco no meio de uma ideia.
5. **Para cada bloco, copie as primeiras 6 a 10 palavras exatamente como estão no texto**, na ordem em que os blocos aparecem. É por elas que o Octopus IA acha o ponto.
6. **Chame `dividir_vsl`.** Se ela disser que não achou o começo de um bloco, copie as palavras de novo, com mais cuidado, e chame outra vez. Nada é gravado enquanto um bloco não for achado.

## A resposta

Depois de gravar, responda com a lista dos blocos, numerada, só com o nome de cada um e uma linha sobre o que ele faz, e diga onde a VSL ficou (no arquivo do chat, na nota do Cérebro, ou nos dois). **Nunca escreva o texto da VSL na resposta**: os blocos são vistos abrindo o arquivo, que já foi atualizado.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
