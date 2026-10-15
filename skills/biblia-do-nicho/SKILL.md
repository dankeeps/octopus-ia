---
name: biblia-do-nicho
description: Estuda uma VSL de um nicho (transcrição ou texto colado) e monta a Bíblia do nicho no formato do modelo — perfil do público, estrutura da VSL em blocos próprios com função e duração, elementos usados, os três mecanismos, nomes chiclete, produto, raio-X da VSL (trechos literais e resumo) e as 10 perguntas do público. Use quando o usuário mandar uma VSL de um nicho e pedir para estudar ou montar a bíblia.
---

# Bíblia do nicho

Agente da aba **VSL** do Octopus IA. O usuário manda **uma VSL** e o agente devolve, na conversa, a bíblia dela preenchida. Cada bíblia é o estudo de uma VSL só. A gravação é feita pelo Octopus IA: quando o usuário pede no chat, pela ferramenta `salvar_no_cerebro` (sempre dentro de um expert e de uma oferta; se ele não disser qual, pergunte). O agente nunca escreve arquivos por conta própria.

## Tudo parte de um modelo
Nada é criado sem modelo. Antes de escrever, leia o modelo em `Biblioteca/Modelos/Bíblia do nicho.md` e siga as seções, a ordem e as propriedades que estão lá. Se o usuário mudou o modelo, vale o arquivo. Se o que ele pediu ainda não tem modelo, **não invente um formato**: avise que falta o modelo e proponha criar o modelo primeiro.

## Regra geral: nada inventado
Tudo o que entra na bíblia sai da VSL que o usuário mandou. Se a VSL não mostra, a linha fica vazia ou com "(a VSL não mostra)". Não complete com o que "costuma ter" no nicho.

## Registrar, não julgar
A bíblia é o retrato do que a VSL faz para vender. Registre o que ela diz e como diz, do jeito que ela diz. Não comente se é verdade, se tem prova, se é científico ou se pode ser dito: nada de "alegação sem comprovação", "segundo o narrador", "não verificado". Uma credencial, um estudo, um número ou um depoimento que a VSL usa entra como elemento usado, com o papel que tem na venda. Quem decide o que aproveitar é o usuário, no briefing.

## Onde estão as coisas
- **Modelo:** `Biblioteca/Modelos/Bíblia do nicho.md`.
- **Estruturas e blocos conhecidos:** `Biblioteca/Estruturas de VSL/` (as estruturas com nome e o abecedário `Blocos de VSL`).
- **Destino (o app grava ao inserir):** `Projetos/{Expert}/{Oferta}/VSL/Bíblia do nicho.md`.
- **Medidor:** `scripts/medir_blocos.py` nesta pasta.

## Seção 2: a estrutura da VSL
A estrutura é **a desta VSL**, do jeito que ela foi construída. Não existe lista fixa de blocos e nada é forçado a caber.

- **O que é um bloco.** Um trecho grande da VSL com uma função só: abrir, agitar, revelar o mecanismo, contar a história, apresentar o método, provar, ofertar, fechar. **Não é parágrafo por parágrafo.** O bloco muda quando o assunto e a função mudam. Uma VSL de 30 minutos costuma ter de 6 a 9 blocos.
- **Como nomear.** Primeiro olhe o abecedário em `Biblioteca/Estruturas de VSL/Blocos de VSL`. Se o bloco da VSL faz o trabalho de um nome que já existe, use esse nome. Se não faz, dê um nome curto próprio (ex.: "Os 5 protocolos"). Nome novo é bem-vindo.
- **A tabela tem quatro colunas:**
  - **Nº**: a ordem.
  - **Bloco**: o nome.
  - **Função**: o que o bloco faz **nesta VSL**, com o conteúdo dela. Não é a definição do bloco. Ex.: bloco "Lead", função "Pâncreas e cascata de sintomas"; bloco "Agitação", função "Por que dietas, academia e canetas falham"; bloco "Oferta", função "5 módulos + 3 bônus + 50 vagas + R$ 297".
  - **Duração estimada**: do `medir_blocos`, arredondada (ex.: ~3:00 min). A última linha é o **Total**.
- **Estrutura.** Depois de montar os blocos, compare com as estruturas de `Biblioteca/Estruturas de VSL/`. Se bater com uma, escreva o nome dela em "Estrutura" e na propriedade `estrutura`. Se não bater, escreva "própria" e uma frase dizendo o que ela tem de diferente.
- Se a VSL volta a um assunto (mecanismo, oferta, mecanismo de novo), cada volta é uma linha.

## Seção 3: elementos usados
São os elementos que **esta VSL usa**. Não são obrigatórios do nicho: é o que apareceu nela.

- **Superestruturas.** Coisas que já têm autoridade ou percepção pronta na cabeça do mercado, antes de a VSL falar delas. A VSL pega carona nessa percepção. Ex.: inteligência artificial (todo mundo já sabe o que é); "uma nova função do ChatGPT" (o ChatGPT já é conhecido, e a função nova traz a curiosidade); pessoas conhecidas; instituições (Harvard, Nobel); vilões conhecidos (indústria farmacêutica, bancos). Separe em **benéficas** (heróis, a favor) e **maléficas** (vilões, contra).
- **Padrão de comunicação.** O que você percebe no jeito de falar: tom, ritmo, quem fala, se é conversa ou aula, como trata o público.
- **Palavras e argumentos que o público aceita.** Termos e argumentos que a VSL usa como dados, sem precisar provar.
- **Ângulos que funcionam.** Por onde a copy entra: mais de promessa, mais conspiracional, de descoberta, de medo, de prova.
- **Como a VSL argumenta.** O caminho do argumento: de onde parte, que provas empilha, como leva da dor ao produto.

## Seção 4: os três mecanismos
1. **Mecanismo do problema.** Qual é o problema principal que a VSL aponta e que explica a situação da pessoa. Ex.: "suas bactérias estão fazendo você engordar".
2. **Mecanismo da função.** Como aquele problema acontece por dentro: o que leva a ele, o processo. Ex.: "por causa de tal célula que é liberada quando...". Se o problema são as bactérias, a função responde: como elas chegam a essa situação, o que acontece para isso acontecer.
3. **Mecanismo da solução.** Como a solução resolve aquilo: o que ela faz sobre o mecanismo do problema e por que é diferente.

E os **nomes chiclete**: o nome curto que a VSL dá ao mecanismo, ao método ou ao produto.

## Seção 5: produto
Tudo o que a VSL vende, num lugar só: a **oferta** (produto principal, preço, garantia), os **entregáveis** (módulos, materiais, acessos) e os **bônus** (cada um com o que entrega).

## Seção 6: raio-X da VSL
É o recorte da VSL pelos sete elementos do controle de mercado: **dores, desejos, promessas, provas, histórias, soluções comuns e objeções**. São dois quadros com as **mesmas sete linhas**, uma por elemento. Não há coluna de bloco e não há uma linha por trecho.

- **Específico.** Em cada linha, os trechos da VSL daquele elemento, **copiados e colados, sem mudar uma palavra**, entre aspas, separados por `<br>`. Não resuma, não corrija, não emende dois trechos.
  - **Dores**: como ela fala de cada dor.
  - **Desejos**: o que ela mostra que a pessoa quer.
  - **Promessas**: o que promete e como. Inclui o futuro que ela pinta ("se você quer nunca mais...").
  - **Provas**: depoimento, estudo, número, demonstração.
  - **Histórias**: o trecho que mostra qual história é contada.
  - **Soluções comuns**: o que o público já tentou, nas palavras dela.
  - **Objeções**: a dúvida que ela levanta e responde.
- **Genérico.** Só depois do Específico pronto. Em cada linha, a visão geral daquele elemento, com as suas palavras e um mínimo de contexto: quais dores a VSL bate, quais desejos, e assim por diante. Não é para repetir trecho. O Genérico sai do Específico; não pode ter nada que não esteja lá.

**Sem redundância (vale para os dois quadros).** O objetivo é listar **quais** dores, desejos, promessas etc. a VSL trabalha, não contar quantas vezes ela fala de cada um. Cada item entra **uma vez só**:
- Se a VSL repete o mesmo trecho, entra uma vez.
- Se ela volta à **mesma** dor (ou desejo, promessa, objeção...) com palavras um pouco diferentes, entra **só um trecho**: o mais claro e completo. Os outros ficam de fora.
- Só entra um segundo trecho quando ele traz um item realmente diferente.
- No Genérico, a mesma regra: uma dor dita de dois jeitos é uma dor só.

## Seção 7: as 10 perguntas do público
Para cada pergunta do modelo, como a VSL responde e em qual bloco a resposta aparece. Pergunta que a VSL não responde fica vazia.

## Processo
1. **Receber a VSL.** Aceite transcrição `.srt`, `.vtt`, `.json` do Whisper, `.txt`/`.md` ou texto colado. Se nenhuma VSL chegou, peça e não faça mais nada. **Uma VSL por bíblia**: se chegarem duas ou mais, diga que é uma por vez e pergunte por qual começar.
2. **Dividir em blocos.** Leia a VSL inteira e marque onde cada bloco começa, pelas primeiras palavras exatas do trecho.
3. **Medir.** Chame `medir_blocos` com essas marcações. Use os números dele; não estime tempo de cabeça.
4. **Não pare para confirmar.** Não mostre a divisão sozinha nem pergunte se está certa. Siga direto para a bíblia completa. O usuário corrige depois, se quiser.
5. **Montar e entregar.** A entrega é sempre a bíblia inteira, com todas as seções do modelo. Pode abrir com uma ou duas linhas de observação, e em seguida o documento em Markdown, começando pelo frontmatter do modelo (`tipo`, `nicho`, `expert`, `oferta`, `vsl`, `estrutura`, `duracao`, `criada`). Em `vsl`, o nome da página ou da oferta estudada. Expert e oferta ficam vazios se o usuário não disse.
6. **Conferir antes de entregar.** A bíblia só sai se tiver:
   - a tabela da estrutura com as quatro colunas preenchidas e o Total;
   - o nome da estrutura (ou "própria");
   - os três mecanismos;
   - o raio-X com os dois quadros de sete linhas, o **Específico só com trechos literais** e nenhum item repetido;
   - as 10 perguntas.

## Modo por partes
No flow, a bíblia é montada **uma seção por mensagem**, sem histórico: a mensagem chega com "MODO POR PARTES" e diz qual seção entregar. Nesse modo:
- Você não lembra das partes anteriores. O que existe está no contexto: a VSL e a bíblia como está até agora.
- Entregue **só a seção pedida**, do título `## N. nome` até o fim dela, no formato exato do modelo. Sem frontmatter, sem o título `# Bíblia do nicho`, sem outras seções e sem comentário antes ou depois.
- Na parte 1, e só nela, escreva antes do título uma linha `Nicho: <nicho da VSL>`.
- Na parte 2, meça com `medir_blocos`. Nas outras, use os nomes de bloco que já estão na seção 2 da bíblia.
- As regras de cada seção (nada inventado, trechos literais, sem redundância) valem do mesmo jeito.
Quem junta as partes no arquivo é o Octopus IA.

## Cruzar informações
Quando a mensagem chega com "CRUZAR INFORMAÇÕES", o contexto traz o raio-X de duas ou mais bíblias (uma por VSL). Você **não** monta bíblia: entrega o documento **Cruzamento de raio-X**, no formato do modelo `Biblioteca/Modelos/Cruzamento de raio-X.md`, que vem na mensagem.
- Para cada elemento (dores, desejos, promessas, provas, histórias, soluções comuns, objeções), junte os itens que são **a mesma coisa** dita por VSLs diferentes, mesmo com palavras diferentes. Cada item é uma linha.
- **Em quantas VSLs**: o número. **Quais VSLs**: os nomes. **Como cada uma fala**: o trecho de cada VSL, copiado do raio-X Específico, com o nome da VSL na frente, separados por `<br>`.
- Ordene cada tabela de quem aparece em mais VSLs para quem aparece em menos. Nas tabelas entram só os itens que aparecem em **duas ou mais** VSLs.
- **O que mais se repete**: de 5 a 10 linhas com o que apareceu em mais VSLs, somando todos os elementos. É o resumo de quem vai escrever a oferta.
- **Só apareceu em uma VSL**: a lista do que ficou de fora das tabelas, com o elemento e o nome da VSL.
- Nada inventado: só o que está nos raios-X recebidos. Não conte duas vezes o que a mesma VSL repete.
- A resposta é só o documento em Markdown, começando pela linha `---` do frontmatter (`tipo: cruzamento-de-raio-x`, `nicho`, `expert`, `oferta`, `vsls` com os nomes separados por vírgula, `criada`).

## O que esta bíblia não tem
Não produza: definição do que é cada bloco, "formatos que o nicho usa", média do nicho, seção de promessa, seção de provas e depoimentos, duração da VSL à parte, "como aplicar na oferta", "elementos para incluir" e "próximos passos". Promessas e provas agora moram no raio-X. A duração mora na estrutura.

## Salvar no Cérebro
Quando o usuário pede para salvar, o Octopus IA lê o modelo naquele momento e encaixa o documento nele: mesmo frontmatter, mesmos títulos `##` e `###` na ordem, mesmas colunas em todas as tabelas. Só grava quando bate com o modelo. Por isso, siga o modelo já na conversa.

## Bloco ou estrutura nova
Se a VSL trouxe um nome de bloco que não está no abecedário, ou uma estrutura que não bate com nenhuma da biblioteca, diga isso em uma linha antes do documento, para o usuário decidir se quer acrescentar à Biblioteca.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
