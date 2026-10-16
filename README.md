# Zelda Restock Helper

Assistente local para acompanhar a página oficial da Gamer Hut. Quando detectar disponibilidade, tenta adicionar uma unidade ao carrinho, abrir o checkout e preencher campos pessoais reconhecidos.

Ele **não faz login automaticamente, não envia o pedido e não realiza pagamentos**. Se necessário, você pode fazer login manualmente na janela persistente do Chromium; a sessão fica salva apenas no perfil local. Você deve revisar os dados, completar os campos não reconhecidos e concluir o pedido manualmente. Não há confirmação de que adicionar ao carrinho ou abrir o checkout reserve estoque.

## Requisitos

- Python 3.10 ou mais recente
- Navegador Chromium instalado pelo Playwright
- Computador ligado e conectado à internet durante o acompanhamento
- Se quiser manter a sessão da loja, faça login manualmente na janela do Chromium do assistente uma vez

## Instalação no Windows

Abra o PowerShell nesta pasta e execute:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Edite o `.env` local e preencha apenas os dados pessoais que deseja automatizar. O programa não pede dados de cartão, CVV, senha ou informações Pix. O CVV deve ser digitado diretamente no checkout, se necessário.

## Uso

```powershell
python watcher.py
```

O programa não consulta a loja entre os lotes. Trinta segundos antes de cada horário anunciado, abre a página do produto em um navegador visível. De 30 segundos antes até 60 segundos depois do lote, mantém essa aba aberta e consulta o HTML da página em segundo plano por `fetch` até duas vezes por segundo; as consultas não fazem a aba navegar ou recarregar. A checagem exige o bloco de compra do produto, o título da edição com capa foil, disponibilidade informada pela página, o link de adicionar ao carrinho dentro desse bloco e quantidade igual a uma unidade.

O Chromium do assistente usa um perfil persistente local em `.browser-profile/`, separado do seu Chrome pessoal. Se a loja exigir conta, faça o login manualmente nessa janela; cookies e armazenamento local serão reutilizados em execuções futuras, até a sessão expirar ou a loja pedir novo login. Não salve senha no `.env` e não use aqui o diretório de perfil do seu navegador cotidiano. Feche qualquer execução anterior antes de iniciar outra, pois o mesmo perfil não deve ser aberto em dois Chromiums ao mesmo tempo.

Para preparar a sessão antes dos lotes, execute `python watcher.py --login`. Faça login na janela aberta e pressione Enter no terminal. Esse modo não monitora produtos nem mexe no carrinho. Depois, use `python watcher.py` normalmente.

Ao detectar disponibilidade, o programa usa a URL de adição ao carrinho fornecida pelo próprio bloco do produto e solicita uma unidade; depois abre o carrinho, tenta avançar para “Finalizar compra” e preenche apenas campos visíveis cujos rótulos reconhece (nome, e-mail, telefone, CPF e endereço). Se não confirmar o item no carrinho ou encontrar ambiguidade, deixa a página aberta para você. Ele para antes de enviar o pedido ou selecionar/pagar.

O aviso sonoro ocorre assim que a disponibilidade é detectada. O bloco do produto é filtrado pelo identificador de catálogo em `config.py`, e o reconhecimento de “Finalizar compra” desconsidera ícones. O programa aguarda o campo de e-mail da primeira etapa do checkout antes de tentar o preenchimento. Uma falha depois de solicitar a adição ao carrinho encerra a consulta automática e deixa a conferência para você, pois uma resposta incerta pode significar que o item já foi adicionado.

Os horários e intervalos estão em `config.py`. Os horários dos lotes usam o fuso de São Paulo (`-03:00`). Ajuste ou remova as datas se a loja alterar o cronograma. Pressione `Ctrl+C` para encerrar.

## Teste imediato no navegador

Com o ambiente virtual ativo, execute:

```bash
python watcher.py --test
```

Esse modo ignora os horários dos lotes e abre imediatamente a página de [Nintendo Switch Sports para Switch](https://www.gamerhut.com.br/nintendo-switch-sports-switch-midia-fisica). Ele confere o estoque uma vez e, se a loja ainda marcar o item como disponível, tenta adicionar uma unidade e abrir o checkout para testar o fluxo. Não lê o `.env`, não preenche dados pessoais e para antes de qualquer pedido ou pagamento. Se o item já estiver indisponível, não tenta adicionar nada e deixa a página aberta para conferência.

Para voltar ao monitor normal do Ocarina of Time, execute `python watcher.py` sem `--test`; os horários e a página original continuam em `config.py`.

## Privacidade e limites

- O `.env` contém dados pessoais em texto simples. Mantenha-o somente no seu computador, não o envie a ninguém e não o adicione ao Git. O `.gitignore` já exclui esse arquivo.
- O perfil `.browser-profile/` contém cookies/sessões de autenticação e também é ignorado pelo Git. Proteja a pasta como protegeria uma sessão já autenticada; apagar a pasta encerra a sessão salva.
- Não coloque número de cartão, CVV, senha ou dados Pix no `.env`. O programa não lê nem preenche dados de pagamento.
- Não usa serviços de CAPTCHA, proxies rotativos ou técnicas para contornar proteções da loja.
- A detecção usa o texto visível da página e pode precisar de ajuste se a Gamer Hut mudar o layout.
- Cada consulta em segundo plano ainda precisa receber uma resposta do site. Duas consultas por segundo podem reduzir a espera de detecção, mas não garantem detectar a mudança antes dos demais compradores. Aumentar ainda mais a frequência pode gerar carga ou acionar limites do site. Carrinho e tela de checkout não garantem reserva; o programa não cria o pedido.
- A loja pode mudar os rótulos e o fluxo do checkout. Se não identificar os controles de forma inequívoca, o programa para e deixa a página aberta para você agir manualmente.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes de fluxo usam Chromium e uma loja fictícia em `127.0.0.1`: verificam a consulta sem navegação, os cookies da adição via `fetch`, o botão de checkout com ícone e a chegada à etapa de e-mail. Eles não enviam pedidos à Gamer Hut e não medem a latência da loja durante um lote. O teste feito no site com Star Fox confirmou o caminho por cliques visuais; não validou o script completo contra o estoque real.
