---
name: controle-de-mercado
description: Alimenta o controle de mercado de uma oferta. Recebe anúncios (do próprio usuário ou de concorrentes), lê cada um, classifica a narrativa e os elementos persuasivos (dores, desejos, promessas, provas, mecanismo e soluções comuns) com os trechos exatos, e entrega o documento que o Octopus IA grava em Controle de mercado, uma nota por anúncio. Só roda quando o usuário invoca com #controle-de-mercado no chat.
barra: true
prefixo: "#"
tipo: funcao
agentes: []
categoria: Criativos
resumo: Recebe anúncios seus ou de concorrentes, cataloga a narrativa e os elementos persuasivos de cada um e grava no controle de mercado da oferta
---

# Controle de mercado

O controle de mercado é o estudo dos anúncios de uma oferta: os do próprio usuário e os de concorrentes. Ele mostra quais dores, desejos, promessas, provas, mecanismos e soluções comuns aparecem, em quantos anúncios, e qual narrativa cada um usa. É a régua para revisar e criar os anúncios daquela oferta. Quem conta é o Octopus IA; o seu trabalho é ler e classificar cada anúncio.

## Onde fica e em que formato

- **Lugar:** `Projetos/{Expert}/{Oferta}/Controle de mercado/Anúncios/`, uma nota por anúncio (CM 01, CM 02…), e o painel `Controle de mercado.md`, que o Octopus IA reconta sozinho. Aparece em Criativos › Controle de mercado.
- **Modelo:** `Biblioteca/Modelos/Anúncio do controle de mercado.md`.
- **Como grava:** você entrega um documento só, no formato abaixo, e o Octopus IA separa em notas. Vale em qualquer chat (de VSL, de Criativos ou outro).

## O que perguntar antes

Pergunte só o que faltar, numa mensagem só:

1. **Os anúncios.** Se não chegaram, peça (texto colado, anexo ou transcrição).
2. **De qual oferta é o controle.** Com o nó Oferta ligado, é a dele. Sem nó e sem o usuário dizer, pergunte, mostrando as que existem (`listar_cofre`). O controle de mercado é sempre de uma oferta do usuário.
3. **De quem são os anúncios:** do próprio usuário ou de concorrente. É obrigatório.
4. **O nome do concorrente**, se forem de concorrente (vai em Anunciante). Use sempre a mesma grafia que já aparece no controle.
5. Se algum anúncio próprio é **validado** (já rodou e deu resultado).

## Como catalogar

Os anúncios chegam de onde vierem: texto colado no chat, anexo, transcrição, inteligência em texto ou em arquivo ligada no flow, ou um anúncio escrito neste chat. Com eles em mãos:
1. Chame `ler_controle_de_mercado` antes de classificar. Ele devolve as ideias que já existem em cada categoria. **Reuse o nome da ideia, letra por letra, sempre que o anúncio trouxer a mesma ideia com outras palavras**; só crie uma ideia nova quando ela não couber em nenhuma. É isso que faz a contagem funcionar.
2. Use `listar_narrativas` para dar a narrativa de cada anúncio pelo catálogo (a virada central). Se nenhuma explica, escreva `NOVA: <nome curto>` e preencha as duas linhas da narrativa nova (ideia e estrutura): ao salvar, o Octopus IA cria essa narrativa na Biblioteca, com o anúncio como exemplo, e ela passa a valer para **todas as ofertas**. Antes de criar, confira de novo o catálogo: narrativa nova é exceção. Se a mesma narrativa nova aparecer em outro anúncio, repita o nome igual.
3. Leia cada anúncio inteiro. Um anúncio = uma transcrição. Nunca junte dois nem classifique o que você não leu. **De quem é cada anúncio é obrigatório:** se o usuário não disser, pergunte uma vez se são anúncios **próprios** ou de **concorrente**, e o nome do concorrente (vai em Anunciante; use sempre a mesma grafia que já aparece em `ler_controle_de_mercado`). Se ele disser que um anúncio próprio é **validado** (já rodou e deu resultado), marque `validado` em Status.
4. De cada anúncio, tire os elementos persuasivos, um por linha, nas seis categorias:
   - **Dor:** o problema que o público sente.
   - **Desejo:** o que ele quer ter ou ser.
   - **Promessa:** o que o anúncio garante (resultado, prazo, condição).
   - **Prova:** o que sustenta (depoimento, estudo, famoso, número, antes e depois).
   - **Mecanismo:** o porquê funciona e o nome do método.
   - **Solução comum:** o que o público já tentou e o anúncio ataca.
   Cada linha tem a **ideia** (nome curto e geral, de 3 a 9 palavras, que serve para qualquer anúncio que diga a mesma coisa) e o **trecho** (a frase do anúncio que carrega a ideia, **copiada palavra por palavra** da transcrição, sem resumir nem corrigir; de 4 a 25 palavras). O trecho exato é o que o Octopus IA compara entre os anúncios. Um anúncio costuma ter de 6 a 14 elementos; a mesma ideia entra uma vez só por anúncio.
5. A transcrição vai **inteira e sem alteração**, em texto corrido (sem os tempos do `.srt`). Só padronize nomes próprios que a transcrição escreveu de vários jeitos.
6. Até **8 anúncios por documento**. Se houver mais, entregue os 8 primeiros e avise que continua no próximo (o usuário insere um lote e pede o seguinte).

A resposta é **só o documento** (ao salvar, o Octopus IA cria uma nota por anúncio em `Controle de mercado/Anúncios/` e reconta o painel; um anúncio repetido dentro do mesmo documento vira cópia, não nota nova; um anúncio que já estava no controle não é gravado nem contado de novo, e o cartão avisa quantos entraram de fato):

**O controle de mercado é sempre de uma oferta do usuário.** Sem saber a qual oferta dele os anúncios pertencem (nó Oferta ligado ou dito na conversa), não classifique: pergunte. Dentro dessa oferta entram os anúncios dele e os de vários concorrentes, cada um com o seu Anunciante. Os anúncios de concorrente são guardados uma vez só no Spy (`Swipe/Controle de mercado/{Anunciante}/`), que é compartilhado entre todos os projetos, e a oferta fica com um atalho; por isso o mesmo anúncio pode ser reaproveitado no controle de mercado de outra oferta sem subir de novo (botão de filtro do controle de mercado › Reaproveitar do Spy).

```
---
tipo: controle-de-mercado
expert: ""
oferta: ""
quantidade: 2
criada: AAAA-MM-DD
---
# Controle de mercado: <de quem são os anúncios>

## Anúncio 1: <título curto que identifica o anúncio>
- **Origem:** <próprio | concorrente>
- **Anunciante:** <nome da página ou do expert>
- **Status:** <validado, só se for anúncio próprio que o usuário disse que validou; senão deixe vazio>
- **Duração:** <segundos, se a transcrição tiver tempo; senão deixe vazio>
- **Narrativa:** <número e nome do catálogo, ex.: 01 O Erro Terrível | NOVA: nome>
- **Ideia da narrativa:** <só se a narrativa for NOVA: em uma ou duas frases, como ela conduz o anúncio>
- **Estrutura da narrativa:** <só se for NOVA: os passos, na ordem, separados por " > ">
- **Narrativa secundária:** <outra que também aparece, ou nenhuma>
- **Formato:** <como aparece na tela, se der para saber pela fala; ex.: fala para a câmera>
- **Por quê:** <uma ou duas frases: o que no anúncio mostra que é essa narrativa>

### Elementos
- Dor | <ideia> | "<trecho exato>"
- Desejo | <ideia> | "<trecho exato>"
- Promessa | <ideia> | "<trecho exato>"
- Prova | <ideia> | "<trecho exato>"
- Mecanismo | <ideia> | "<trecho exato>"
- Solução comum | <ideia> | "<trecho exato>"

### Transcrição
<o anúncio inteiro>
```

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
