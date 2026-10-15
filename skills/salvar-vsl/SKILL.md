---
name: salvar-vsl
description: Sobe uma oferta e a VSL dela para o Cérebro. Cria a oferta com as pastas padrão se ela ainda não existe, pergunta a versão e o nome, pede o script se faltar, pergunta se é para dividir em blocos e guarda a VSL no modelo, usando o arquivo que o usuário mandou (sem reescrever). Só roda quando o usuário invoca com #salvar-vsl no chat.
barra: true
prefixo: "#"
tipo: funcao
agentes: []
categoria: VSL
resumo: Cria a oferta (se ainda não existe) com as pastas padrão e guarda a sua VSL nela, com a versão e a divisão em blocos
---

# Salvar VSL

Esta função sobe uma oferta para o Cérebro junto com a VSL dela. Você recebe a VSL que o usuário já tem (a que está no ar ou a que vai ser gravada) e a guarda no modelo de VSL, com a ferramenta `cadastrar_vsl`. Não é para escrever VSL nova nem para melhorar a que chegou.

**Você não reescreve o texto.** A ferramenta pega o arquivo que o usuário mandou (o texto colado ou o anexo) e grava como está. O seu trabalho é conduzir o cadastro: confirmar a oferta, juntar os dados e dizer onde cada bloco começa.

## A oferta e as pastas padrão

Toda oferta do Octopus IA fica em `Projetos/{Expert}/{Oferta}/` e tem sempre as mesmas pastas:

- **VSL**: a VSL da oferta (uma nota por versão: VSL V1, VSL V2…), a bíblia do nicho e o briefing de tese.
- **Criativos** (pasta `Anúncios`): os anúncios, em remessas, e os validados.
- **Big ideas**.
- **Mapa do mercado**: o controle de mercado (`Controle de mercado`), as personas (`Personas`) e o dicionário da oferta.

Se a oferta ainda não existe, a ferramenta `cadastrar_vsl` cria a oferta já com essas pastas (e o expert, com Credenciais e História, se ele também for novo). Antes, confirme com o usuário, em uma frase, o que vai ser criado. Só chame com `criar: true` depois do sim.

## O passo a passo da conversa

Pergunte só o que faltar, tudo numa mensagem só, e espere a resposta:

1. **O script da VSL.** Vem colado na mensagem, anexado, ou ligado no flow. Se não chegou, peça.
2. **O expert e a oferta.** Com o nó Oferta ligado, use o que está nele. Sem nó e sem o usuário dizer, pergunte, mostrando o que existe (`listar_cofre`).
3. **O nome da VSL e a versão** (V1, V2…). Se a oferta já tem VSLs (`listar_notas` na pasta VSL dela), diga quais são e pergunte se esta é a próxima. Não escolha a versão sozinho. Sem nome, vale o nome da oferta.
4. **Se é para dividir em blocos.** Pergunte: "Quer que eu divida a VSL em blocos?" Se o script já veio com os blocos marcados, diga que vai manter os dele.

O resto é opcional e você não precisa perguntar: nicho, data em que foi feita, link (normalmente do Drive ou da página), play rate, retenção no primeiro minuto, retenção até o pitch e conversão. Informe só o que o usuário disse. **Nunca invente métrica, link ou data.** Porcentagem entra como número, sem o sinal (38 e não 38%).

## Os blocos

Dividir em blocos é marcar onde cada um começa. Em `blocos`, mande o nome do bloco e as **primeiras 6 a 10 palavras dele, copiadas exatamente do texto**, na ordem em que aparecem. O Octopus IA põe o título no ponto certo e o texto continua igual.

- **Se o script já veio dividido** (títulos, numeração, marcações), use essa divisão e esses nomes.
- **Se veio em texto corrido**, divida você. Cada bloco é um trecho que cumpre uma função na VSL (abrir e prender, contar a história, mostrar o problema, revelar a causa, apresentar o mecanismo, apresentar o produto, fazer a oferta, fechar). Dê a cada bloco um nome curto que diga o que ele faz. Use quantos blocos o texto tiver.
- Se a ferramenta disser que não achou o começo de um bloco, copie as palavras de novo do texto, com mais cuidado, e chame outra vez. Nada é gravado enquanto um bloco não for achado.
- Se o usuário não quiser blocos, chame sem `blocos`: a VSL é gravada inteira.
- A transcrição de um vídeo não é feita aqui: se o usuário só tem o vídeo, diga para transcrever na aba Transcrição (ou no nó de Transcrição do flow) e mandar o texto.

## A entrega

Chame `cadastrar_vsl`. Depois, responda em uma ou duas frases: onde a VSL ficou, a versão e em quantos blocos foi dividida. Não escreva a VSL na resposta.

Se o expert ou a oferta não existem, a ferramenta avisa. Pergunte ao usuário se é para criar e só então chame de novo com `criar: true`. Se a versão já existe na oferta, pergunte se é para trocar (`substituir: true`) ou se é outra versão.

## Salvar é fazer, não dizer
Quando o usuário mandar salvar (ou responder sim), grave nesta mesma resposta pela ferramenta. Escrever o conteúdo no chat não é salvar. Não diga que salvou sem a ferramenta ter respondido com sucesso, e não termine a resposta em "vou salvar". Depois de gravar, responda em uma linha onde ficou; se não deu, diga que nada foi salvo e por quê.
