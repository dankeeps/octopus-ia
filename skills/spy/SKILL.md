---
name: spy
description: Spy do Octopus IA — pesquisa a Biblioteca de Anúncios da Meta por palavra-chave num navegador próprio, confere cada anunciante (anúncios ativos e há quanto tempo estão no ar), acompanha as bibliotecas monitoradas e grava bibliotecas, histórico e relatório no Cérebro. Não gasta IA.
---

# Spy

Aba **Spy** do Octopus IA, com duas telas: **Busca** e **Bibliotecas**. A pesquisa roda dentro do Octopus IA, num navegador próprio.

## Peças
- `spy/coletor.mjs` — Playwright + Chromium próprio em `spy/browsers`, perfil em `spy/perfil`, na pasta de dados do aplicativo
  (separado do navegador da pessoa). Busca com anúncios ativos, ordenada por impressões, rola até 40
  anúncios por palavra, acha a biblioteca de cada anunciante pela busca da própria Meta e lê a contagem.
- `spy.py` — roda uma busca por vez, guarda o histórico em `spy/buscas/` (pasta de dados do aplicativo) e grava no Cérebro.
- Instalação: feita pelo `instalar.py` (precisa do Node.js).

## Busca
1. Palavras: até 10. Os chips vêm de `Biblioteca/Palavras-chave Spy.md` (seção do nicho do projeto, PT / EN / Latam).
   Regra: palavra do nicho + palavra do mercado, ou o nome chiclete da oferta.
2. Filtros: país, mínimo de anúncios ativos, tempo mínimo no ar (pelo menos um anúncio ativo iniciado há X dias),
   quantas bibliotecas achar.
3. **Monitoradas** (`monitoramento: true`) do nicho são conferidas no começo de toda busca, mesmo que a palavra não as traga.
4. Se a Meta travar (login, cookies, verificação): o Octopus IA avisa, a pessoa abre o navegador do Spy, resolve e clica em Continuar.
5. Resultado: **Bibliotecas** (passaram nos filtros + monitoradas) e **A conferir** (não deu para confirmar).
   Blacklist direto do cartão.

## Gravar no Cérebro
Botão no fim da busca. Encaixa nos modelos da Biblioteca (`Biblioteca/Modelos/Spy página.md` e `Relatório de Spy.md`):
- `Swipe/Spy/<Nicho>/<Página> (Spy)/<Página> (Spy).md` + `Criativos/` + `Funil/` — mesma página (page_id ou nome)
  é atualizada: anúncios ativos, variação contra o Spy anterior, histórico `AAAA-MM-DD · N` (um por dia), palavras.
- `Swipe/Spy/Relatórios/Spy AAAA-MM-DD <Nicho>.md` — tabela página, ativos, variação, monitorada, palavra, link.
- `Swipe/Spy/Blacklist.md` — nunca entra. `Swipe/Spy/Spy.md` — nota de abertura (criada se não existir).

## Bibliotecas
Lê do Cérebro as notas `tipo: spy_pagina`: ativos, variação, histórico em barrinhas, liga/desliga monitoramento
(grava a propriedade na nota), links para a biblioteca da Meta e para a nota.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
