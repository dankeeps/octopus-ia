---
name: salvar-expert
description: Guarda as credenciais e a história de um expert no Cérebro. Recebe o que o usuário conta ou manda (texto, transcrição, anotações), lê as notas do expert, que já nascem do modelo, e escreve o conteúdo embaixo do título certo de cada seção, no lugar certo. Só roda quando o usuário invoca com #salvar-expert no chat.
barra: true
prefixo: "#"
tipo: funcao
agentes: []
categoria: Expert
resumo: Recebe as credenciais e a história do expert e grava nas duas notas dele, no formato do modelo e no lugar certo
---

# Salvar expert

Esta função guarda o que o usuário sabe do expert nas duas notas que todo expert tem. Elas valem para todas as ofertas dele e são a base da VSL e dos anúncios em primeira pessoa.

## Onde fica e em que formato

- **Credenciais:** `Projetos/{Expert}/Credenciais.md`. Modelo: `Biblioteca/Modelos/Credenciais.md`.
- **História:** `Projetos/{Expert}/História.md`. Modelo: `Biblioteca/Modelos/História.md`.

As duas notas já existem na pasta do expert, criadas a partir do modelo: têm o cabeçalho, os títulos das seções e uma linha de dica (a que começa com `>`) em cada seção. **Você não cria nota nova nem muda de lugar: você escreve dentro delas**, com a ferramenta `editar_nota`.

O formato é o do modelo, sem mudar:
- o cabeçalho (`---` … `---`) fica como está;
- os títulos das seções ficam iguais e na mesma ordem;
- o conteúdo entra embaixo do título da seção a que pertence;
- na seção que você preencheu, tire a linha de dica; nas que continuam vazias, deixe a dica.

## O passo a passo

1. **Qual expert.** Com o nó Oferta ligado, é o expert dele. Sem nó e sem o usuário dizer, pergunte, mostrando os que existem (`listar_cofre`). Se o expert ainda não existe, confirme com o usuário e crie com `criar_oferta` (só o expert, sem oferta): as duas notas nascem junto.
2. **Leia as duas notas** (`ler_nota`) para ver o que já está escrito. Nunca apague o que já está lá sem o usuário pedir.
3. **Receba o material.** Pode ser o usuário contando no chat, um texto colado, uma transcrição de conversa com o expert ou anotações. Se ele não mandou nada, peça. Se ele preferir, faça você as perguntas, seção por seção, poucas de cada vez.
4. **Separe o que é de cada nota.** O que dá autoridade (formação, números, resultados de alunos, mídia, provas, o que não pode ser dito) vai para Credenciais. A trajetória contada (o antes, o problema, o que tentou, a descoberta, a virada, a missão, falas marcantes) vai para História. O mesmo material costuma alimentar as duas.
5. **Grave com `editar_nota`**, uma nota por vez, mandando a nota inteira com o conteúdo novo no lugar.
6. **Diga o que entrou**, em lista curta: quais seções de cada nota foram preenchidas e quais continuam vazias por falta de informação.

## Regras

- **Estas duas notas são o registro do que o expert tem de verdade**: é delas que os outros agentes tiram o que é dele. Entra o que o usuário disse ou o que está no material dele. Se o material diz "muitos alunos", escreva isso e pergunte o número.
- **Quando o material é uma VSL de referência (de outra pessoa)** e o usuário pede para preencher com base nela: preencha, sem julgar e sem avisos ("alegação", "sem comprovação", "isso é do narrador"). Escreva cada item como o equivalente que o expert precisa ter naquele lugar, seguido de `[confirmar]`, para ele trocar pelo dele. Diga em uma linha, no chat, que os itens marcados vieram da referência e esperam o dado dele.
- Número entra exato, com a data ou o período quando houver.
- A história fica na voz do expert, com as cenas e os detalhes que ele deu. Não enfeite nem resuma o que é concreto.
- Em "O que não pode ser dito" só entra o que o usuário mandou vetar.
- Para mudar algo que já está escrito, mude só o trecho pedido e mantenha o resto igual.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
