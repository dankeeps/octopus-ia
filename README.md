# Octopus IA

O primeiro sistema de IA feito para direct response. O Octopus IA orquestra agentes, skills e contexto para você criar VSLs e criativos, estudar o que o mercado está escalando e organizar tudo num só lugar.

Ele roda no seu computador (Mac ou Windows), abre no navegador e usa a sua própria conta do ChatGPT. Não precisa de chave de API.

**O que vem nele:** Spy da Biblioteca de Anúncios da Meta, monitoramento de concorrentes, automações no horário que você escolher, transcrição de vídeos no próprio computador, leitura de vídeos do YouTube, TikTok e Instagram por link, a Bíblia da VSL, o Briefing de tese, a escrita da VSL bloco por bloco, os agentes de criativo, o controle de mercado, as personas e o Cérebro, onde ficam todos os experts, ofertas, VSLs e anúncios.

---

## Instalar (o jeito fácil)

1. Baixe este projeto: no GitHub, botão **Code › Download ZIP**. Descompacte e deixe a pasta em **Downloads** com o nome **Octopus**.
2. Abra o **Claude Code** ou o **Codex** e mande esta mensagem:

```
Na minha pasta Downloads tem um projeto chamado Octopus. Instale ele para mim:
leia o arquivo README.md que está dentro dele e siga a seção "Instruções para o assistente",
do começo ao fim, no meu sistema (Mac ou Windows). No final, me diga se tudo ficou instalado
e onde está o ícone para abrir.
```

3. No fim, aparece o ícone **Octopus IA** na área de trabalho. É só clicar para abrir.
4. No primeiro uso, entre com a sua conta do ChatGPT em **Configurações** (ou no nó ChatGPT de um flow).

## Atualizar

Quando sair uma versão nova, abra o Claude Code ou o Codex e mande:

```
Atualize o Octopus IA que está instalado no meu computador: leia o README.md da pasta dele
e siga a seção "Como atualizar".
```

Atualizar troca os arquivos do programa e traz as notas novas da Biblioteca. Seus projetos, VSLs, anúncios, conversas, o login do ChatGPT e as configurações ficam fora da pasta do programa e não são tocados. Na Biblioteca, o que você criou fica como está, e o que for trocado vai para a lixeira do Octopus IA.

## Onde ficam os seus dados

| O quê | Onde |
|---|---|
| Projetos, notas, VSLs, anúncios, a Biblioteca (o Cérebro) | `Octopus IA`, na sua pasta de usuário |
| Login do ChatGPT, conversas, configurações, navegador do Spy, Whisper | Mac: `~/Library/Application Support/Octopus IA` · Windows: `%LOCALAPPDATA%\Octopus IA` |
| O programa | a pasta onde você instalou (esta) |

Para fazer backup, use **Configurações › Arquivos** dentro do Octopus IA: ele copia tudo para a pasta que você escolher (pode ser o Google Drive).

---

## Instruções para o assistente

Estas instruções são para o Claude Code ou o Codex que vai instalar o Octopus IA. Siga na ordem. Use os comandos do sistema da pessoa (Mac ou Windows). Explique cada passo em uma frase, em português, sem jargão. Peça confirmação antes de instalar programas no computador dela.

### 1. Ache a pasta
O projeto está em `~/Downloads/Octopus` (Mac) ou `%USERPROFILE%\Downloads\Octopus` (Windows). Se a pasta tiver outro nome (por exemplo `Octopus-main` ou `octopus-ia-main`, que é o nome que o GitHub dá ao ZIP), use essa. Ela tem o arquivo `servidor.py`. Se o ZIP ainda não foi descompactado, descompacte.

Recomendado: mova a pasta para um lugar fixo antes de instalar, porque o ícone aponta para ela.
- Mac: `~/Octopus IA App`
- Windows: `%USERPROFILE%\Octopus IA App`

Não mova a pasta depois de instalar. Se precisar mover, rode a instalação de novo.

### 2. Python 3.11 ou mais novo
Confira com `python3 --version` (Mac) ou `py -3 --version` (Windows).
- Mac sem Python 3.11+: `brew install python@3.12` (se não houver Homebrew, instale pelo site https://brew.sh ou use o instalador de https://www.python.org/downloads/macos/). O `python3` que vem com o Mac (3.9) não serve.
- Windows sem Python 3.11+: `winget install -e --id Python.Python.3.12`. Depois feche e abra o terminal.

Daqui em diante, `PY` é esse Python: no Mac, `python3.12` (ou o caminho completo dele); no Windows, `py -3.12`.

### 3. Node.js 18 ou mais novo
Confira com `node --version`.
- Mac: `brew install node`
- Windows: `winget install -e --id OpenJS.NodeJS.LTS`, depois feche e abra o terminal.

### 4. Rode o instalador
Dentro da pasta do projeto:

```
PY instalar.py
```

Ele faz, sozinho:
- instala o Codex (`npm install -g @openai/codex`), que é como o Octopus usa a conta do ChatGPT da pessoa;
- cria o ambiente do Whisper (transcrição no computador) com o leitor de vídeos e o ffmpeg;
- baixa o modelo de transcrição (cerca de 1,5 GB, demora alguns minutos na primeira vez);
- instala o navegador próprio do Spy;
- cria o ícone **Octopus IA** na área de trabalho (no Mac também em `~/Applications`; no Windows também no menu Iniciar);
- confere tudo no fim e mostra o que ficou com ✓ e o que ficou com ✗.

Se algum passo der erro, leia a mensagem: o instalador diz o que falta. Resolva e rode de novo `PY instalar.py --atualizar` (ele é seguro para rodar mais de uma vez).

Problemas comuns:
- **Windows, erro de permissão no `npm install -g`:** rode o terminal normal (não precisa de administrador); se persistir, `npm config set prefix "%APPDATA%\npm"` e rode de novo.
- **Windows, o Whisper não abre (erro de DLL):** instale o Microsoft Visual C++ Redistributable (`winget install -e --id Microsoft.VCRedist.2015+.x64`).
- **Windows, nomes de arquivo muito longos:** se aparecer erro de caminho longo ao salvar, ative caminhos longos (precisa de administrador): `reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f`.
- **Mac, `npm install -g` pede senha ou dá erro de permissão:** instale o Node pelo Homebrew (passo 3) e rode de novo.

### 5. Abra e confira
Abra pelo ícone da área de trabalho, ou rode `PY ligar.py`. O navegador abre em `http://localhost:5178`.

Conferência rápida (opcional): `PY instalar.py --conferir` lista tudo o que está instalado.

### 6. Diga à pessoa
- que o ícone **Octopus IA** está na área de trabalho;
- que no primeiro uso ela precisa entrar com a conta do ChatGPT em **Configurações › ChatGPT**;
- que, para o Spy funcionar, na primeira busca pode aparecer um aviso da Meta (login ou verificação): ela clica em **Abrir o navegador do Spy**, resolve e clica em **Continuar**.

---

## Como atualizar

Instruções para o assistente que vai atualizar o Octopus IA.

1. Ache a pasta onde o Octopus IA foi instalado. O ícone da área de trabalho aponta para ela; o arquivo `instalacao.json` na pasta de dados do aplicativo (Mac: `~/Library/Application Support/Octopus IA`, Windows: `%LOCALAPPDATA%\Octopus IA`) também guarda o caminho em `"pasta"` e o Python usado em `"python"`.
2. Dentro dela, com o mesmo Python da instalação, rode:

```
PY atualizar.py
```

Ele confere a versão no repositório, baixa a nova, desliga o Octopus IA, troca só os arquivos do programa e roda o instalador de novo para conferir as dependências. No fim mostra o que mudou.

3. Peça para a pessoa abrir o Octopus IA de novo pelo ícone e recarregar a página do navegador, se estiver aberta.

Nunca apague a pasta de dados do aplicativo nem a pasta `Octopus IA` da pessoa: é ali que estão os projetos dela.

---

## Para quem usa pelo terminal

```
python3 instalar.py              # instala tudo e cria o ícone
python3 ligar.py                 # abre o Octopus IA
python3 ligar.py --parar         # desliga
python3 atualizar.py             # atualiza para a versão mais nova
python3 instalar.py --conferir   # mostra o que está instalado
```

## Versão

A versão instalada está no arquivo `VERSION` e no rodapé de **Configurações**. O que mudou em cada versão está no `CHANGELOG.md`.
