---
name: ultra-modelagem
description: Ultra modelagem de anúncio. Pega um anúncio de referência (concorrente ou outro nicho), tira a ideia central dele, constrói a narrativa em volta dela com os gatilhos do interesse e o tom argumentativo, e busca cada argumento no controle de mercado da oferta. Só roda quando o usuário invoca com /ultra-modelagem no chat.
barra: true
agentes: [anuncio]
categoria: Criativos
biblioteca: [Gatilhos do interesse, Tom argumentativo]
resumo: Tira a ideia central de um anúncio de referência e escreve a nossa versão com os argumentos do controle de mercado
---

# Ultra modelagem

Esta skill só vale no pedido em que o usuário escreveu `/ultra-modelagem`. Fora dele, não use nada daqui.

**O princípio: nada é criado do zero.** O anúncio novo junta três coisas que já existem:
- a **ideia central** de uma referência: um anúncio de concorrente, um Reels, um vídeo viral, de qualquer nicho;
- os **gatilhos do interesse** e o **tom argumentativo** da Biblioteca, que são o jeito de contar a ideia de forma que prenda;
- os **argumentos do controle de mercado da oferta**: dores, desejos, promessas, provas, mecanismo e soluções comuns.

**Um nome só para a mesma coisa:** quando o usuário diz "elementos persuasivos", é o que está no **controle de mercado** da oferta, montado com os anúncios dele e dos concorrentes. Esse banco já existe: você não o monta de novo, você o consulta.

Todas as regras fixas da skill de anúncio continuam valendo: nó Oferta obrigatório, remessa e numeração, nome só com a sigla, roteiro em parágrafos, vícios de IA.

## A lógica, em uma linha
**Ideia central da referência → narrativa construída em volta dela com os gatilhos do interesse e o tom → argumentos buscados no controle de mercado, um a um, na hora de escrever.**

| Pergunta | Resposta | De onde vem |
|---|---|---|
| Sobre o quê é o anúncio? | a ideia central | do anúncio de referência |
| Como eu conto de um jeito que prenda? | curiosidade, mistério, novidade, o ângulo de entrada | `Biblioteca/Gatilhos do interesse` e `Biblioteca/Tom argumentativo` |
| O que eu afirmo? | dores, desejos, promessas, provas, mecanismo, soluções comuns | o controle de mercado da oferta |

O hook costuma abrir com a ideia, mas não é regra: às vezes o hook prende e a ideia vem logo depois.

## O que você precisa
- **A referência.** Pode ser anúncio, Reels ou vídeo viral. Colada na mensagem, ou indicado pelo número no controle de mercado (aí leia inteiro com `ler_anuncio_do_controle`). Sem ele, peça.
- **O nó Oferta ligado ao chat. É obrigatório.** É ele que diz de qual controle de mercado os argumentos saem. Se o contexto não trouxer "Oferta deste flow", não rode a skill: peça para o usuário ligar o nó Oferta e pare. Nunca escolha uma oferta por conta própria nem use o controle de mercado de outra.
- **Os anúncios da própria oferta.** Antes de escrever, leia os anúncios que a oferta já tem: os do usuário no controle de mercado (`ler_controle_de_mercado` com a base `meus`, e os validados inteiros com `ler_anuncio_do_controle`) e os já salvos nas remessas (`listar_oferta`, `ler_nota_oferta`). É deles que sai o mecanismo.
- **O controle de mercado dessa oferta.** Sem controle de mercado na oferta, avise e peça para alimentar antes: sem ele não há de onde tirar os argumentos.
- Um pedido pode trazer mais de uma referência: cada uma vira um anúncio novo.

## O método

### 1. Ache a ideia central da referência
Leia a referência inteira e dê um nome curto à ideia central: aquilo em volta do qual o anúncio inteiro foi construído. Tudo o que o anúncio diz existe para contar essa ideia.

| Referência | Ideia central |
|---|---|
| Um personagem que fala como se fosse o salário da pessoa e mostra os quatro perfis de quem vende pela internet | **Os perfis de vendedor** |
| "Ninguém te ensinou duas coisas": escolher o produto antes e a ordem dos anúncios | **Dois segredos: o produto e a ordem** |
| A pessoa que trabalha o mês inteiro e o dinheiro acaba no dia 20 | **O dinheiro que acaba antes do mês** |

Teste: tire a ideia e veja se o anúncio desmonta. Se ele continua de pé, você pegou um detalhe, não a ideia.
- A ideia tem que caber na oferta: o mecanismo e a chamada da oferta precisam conseguir entregar o que ela promete. Se não couber, avise.
- **Olhe também a imagem**, não só a fala. Muita coisa da ideia está na tela e não é dita (no exemplo, os quatro formatos aparecem desenhados e o locutor nem diz os nomes). Use o campo Formato do controle de mercado e, se houver o vídeo, o que aparece nele.
- **Dramatize e diga na língua da oferta.** "Trabalho muito e nunca sobra" virou "Trabalho há anos, pego hora extra, e mesmo assim no dia 20 a conta já tá no vermelho".

### 2. Construa a narrativa em volta da ideia
É aqui que o anúncio fica interessante, e é aqui que ele fica **muito diferente do original**. Com a ideia na mão, você constrói um jeito de contá-la:
- **A narrativa é livre.** Você não precisa encaixar numa narrativa do catálogo, nem seguir a ordem da referência. Ela pode começar de um jeito e virar para outro, desde que tudo sirva à ideia. Se uma narrativa do catálogo ajudar, use; se não, construa a sua.
- **O banco de ganchos.** Para a abertura, consulte `listar_ganchos` e `ler_gancho` (as fórmulas por gatilho e a lista geral) e preencha com a ideia e com as palavras do controle de mercado.
- **O formato e o hook.** Pergunte: como eu abro isso de um jeito que prenda e pareça orgânico? Pense na cena, não só na frase (o expert segurando perto da câmera um papel com os quatro perfis, em tela dividida com a tela do celular). O formato é escolhido para a ideia e é diferente do da referência.
- **O tom argumentativo** (nota da Biblioteca): o ângulo pelo qual a ideia entra. Dica de ouro, grande erro, o que ninguém te explica, história pessoal.
- **Os gatilhos do interesse** (nota da Biblioteca): o que mantém a pessoa ouvindo de uma batida para a outra. Curiosidade ("existe algo que você precisa fazer antes disso… dá uma olhadinha nisso daqui"), mistério, novidade, injustiça ("o problema nunca foi…").

O que faz a copy prender é pensar, a cada trecho, **por que a pessoa continuaria ouvindo**. Os gatilhos do interesse são a resposta: um anúncio que só afirma, sem abrir curiosidade nem criar expectativa, é abandonado mesmo com os argumentos certos.

**A referência é apoio, não molde.** Ajuda escrever com ela ao lado, para ver o que cada trecho dela faz e decidir o que fazer com isso. Não é para seguir a ordem dela:

| Decisão | Quando |
|---|---|
| **Reescrever** com as nossas palavras | a batida serve à ideia |
| **Cortar** | ficou cansativa, ou o anúncio passa do tamanho da referência |
| **Trocar** por um argumento do controle de mercado | o que ela diz é do concorrente (mecanismo, prova, autoridade) |
| **Acrescentar** | a referência deixou um buraco que nós conseguimos preencher |

### 3. Na hora de cada argumento, vá ao controle de mercado
Toda vez que a narrativa pedir um argumento, **busque no controle de mercado antes de escrever**. Use `ler_controle_de_mercado` (comece pelos validados do usuário) e, para ver a frase inteira, `ler_anuncio_do_controle`.

| A narrativa pede | Você busca no controle de mercado |
|---|---|
| o que incomoda a pessoa | Dores |
| o que ela quer | Desejos |
| o que ela já tentou | Soluções comuns |
| o que nós prometemos | Promessas |
| por que funciona | Mecanismo |
| por que acreditar | Provas |

- **O controle de mercado trava a substância, não a forma.** Qual dor, qual desejo, qual promessa e qual mecanismo vêm do controle de mercado. Como isso é dito é livre: crie a cena, o exemplo, a comparação. O controle de mercado diz "a pessoa não tem dinheiro para comprar o que quer"; o anúncio pode dizer "tem gente que está com o mesmo carro há dez anos porque nunca sobra pra trocar". Isso não precisa estar escrito lá.
- **O que não se inventa** é a dor ou o desejo em si (um que o público da oferta não tem), o mecanismo, e o dado sobre o próprio expert ou sobre terceiros com nome: anos de experiência, número de alunos, pessoa famosa, preço.
- **Prova e depoimento você pode criar.** Se a narrativa pede um caso, um antes e depois ou um depoimento, escreva o que encaixa melhor na ideia e marque com `[Prova a conferir: precisa de <o que tem que existir de verdade>]`. O usuário confere no material dele antes de gravar. Não cite código do controle de mercado no roteiro; descreva o material.
- **Não se apoie sempre na mesma prova.** "Testei com os meus alunos" não entra em todo anúncio. A credibilidade também vem da lógica do mecanismo, de uma realidade que a pessoa reconhece e de uma demonstração na tela.
- O argumento vem do controle de mercado, mas é dito de outro jeito, a serviço da ideia nova. Não repita igual o argumento que já carrega outro anúncio do usuário: diga qual você evitou repetir.
- O que é do concorrente não vira nosso: prova, número, autoridade, nome de mecanismo e escassez dele ficam de fora.

### 4. O mecanismo é sempre o nosso
A referência tem o mecanismo do concorrente. Ele nunca entra no nosso anúncio, nem com outro nome.
- O mecanismo do anúncio novo é um dos que os anúncios da própria oferta já usam, com o nome que eles dão. Por isso a leitura dos anúncios da oferta é obrigatória antes de escrever.
- A oferta pode ter mais de um jeito de apresentar o mecanismo (ex.: "a vitrine pronta", "Método Vitrine em 3 Passos", "os três anúncios na ordem certa"). Escolha o que conta melhor a ideia nova, e pode variar de um anúncio para o outro: são todos nossos.
- Se a ideia da referência só fecha com o mecanismo do concorrente (ele promete uma coisa que o nosso não faz), a ideia não serve para esta oferta. Ela não entra na lista de ideias.
- Em Método de copy, diga qual mecanismo usou e de qual anúncio nosso ele veio.

### 5. Regras de escrita desta skill
- **Nenhuma frase copiada.** A batida pode ficar; as palavras são nossas.
- **Tamanho da referência.** Se ela é curta, a nossa versão é curta. Trecho que só alonga sai.
- **Mais prova que a referência.** Onde ela afirma, nós mostramos: um caso concreto e a prova do controle de mercado.
- **"Fazer", não "saber".** A pessoa não quer ser aluna aprendendo uma coisa; quer o resultado. "Existe algo que você precisa **fazer** antes disso", não "que você precisa saber".
- **A chamada é a da oferta.** O destino é o que a oferta tem de verdade (aula, quiz, VSL). Se a referência manda para um tipo de página que a oferta não tem, use a nossa.
- **Marque a cena entre colchetes** quando a ideia depende do que aparece: `[Expert mostrando o papel com os 4 perfis]`.
- **Releia do começo.** A cada batida escrita, releia o anúncio desde a primeira frase, em voz alta. O que soar repetido, cansativo ou sem ligação com a frase anterior, mude ou corte.

## Como entregar
Em duas respostas, e as duas são limpas.

**Primeira resposta: só as ideias.** Nada de plano, tabela ou explicação do método. Uma lista numerada com as ideias que você tirou da referência: a central primeiro, depois as outras que também dariam um anúncio.

```
Ideias deste anúncio:

1. **<nome curto da ideia central>** (central): <uma linha dizendo o que é>
2. **<nome curto>**: <uma linha>
3. **<nome curto>**: <uma linha>

Qual número?
```

- De três a seis ideias. Cada uma tem que aguentar um anúncio sozinha; detalhe solto não entra na lista.
- Só entram ideias que cabem na oferta (o nosso mecanismo e a nossa chamada conseguem entregar). A que não couber fica de fora.
- Se o usuário já disse a ideia no pedido ("faz com a ideia dos formatos"), pule a lista e escreva.

**Segunda resposta: o anúncio.** Quando ele responder com o número (ou os números: cada ideia escolhida vira um anúncio), escreva direto. A resposta é só o documento de anúncios, no formato da skill de anúncio, sem texto antes nem depois.

O que você decidiu no caminho vai nas propriedades do documento, não numa explicação:
- **Big idea:** a ideia escolhida, dita como tese.
- **Narrativa:** a do catálogo se a sua construção coincidir com uma; se não, "Livre (ultra modelagem)".
- **Método de copy:** "Ultra modelagem do <referência>: ideia <qual>; mecanismo <o nosso, de qual anúncio>; formato <qual>; argumentos do controle de mercado". Se evitou repetir um argumento de outro anúncio nosso, ou se faltou algum argumento no controle de mercado, diga aqui.

## O que não pode
- Inventar uma dor, um desejo ou um mecanismo que o controle de mercado não tem, ou um dado do expert (anos, número de alunos, famoso, preço). A forma de dizer é livre, e prova criada leva a marcação `[Prova a conferir: …]`.
- Copiar frase da referência, manter o formato e os personagens dela, ou entregar algo que pareça uma versão do original.
- Usar o mecanismo do concorrente, com o nome dele ou disfarçado.
- Trazer prova, número, autoridade ou escassez do concorrente.
- Passar do tamanho da referência sem motivo.

Os exemplos resolvidos pelo usuário estão em `referencias/exemplos.md`. Estude o movimento, não as frases.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
