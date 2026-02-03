# 🛡️ IDENTIDADE REJEITADA (IRS)

> "Disciplina não vem de força de vontade, mas da ausência de escolha."

Este sistema é um framework de Modificação Comportamental. Ele utiliza conceitos de arquitetura de escolha restritiva, punição por aversão e gamificação de "skin in the game" para garantir que você não escape da rotina que você mesmo criou. Sua principal função é o disparo de "rejeições", frases que contrariam suas crenças criando uma dissonância cognitiva com o objetivo de gerar desconforto imediatamente e gerar energia para te mover no sentido dos seus objetivos.

---

# Principais Funções

## .: PLAY REJECTIONS :.

A cada 1 a 3 minutos, uma rejeição é tocada. Ela exibe três popups com três frases diferentes; os popups podem ser exibidos em locais diferentes do monitor. O volume do computador é setado em 100 para cada rejeição.

## .: CONTRATO DE SILÊNCIO :.

Para estudar ou trabalhar, você assina um contrato de 30 ou 60 minutos para desativar as rejeições. O sistema te monitora: 3 ou 4 vezes, em momentos aleatórios, o app verifica se você está realmente fazendo o que disse que faria.

Quando o tempo acabar, você precisa fazer um novo contrato.

## .: INTERVALOS :.

Existem 2 pausas que podem ser usadas diretamente no Contrato de Silêncio: Intervalo de 10 minutos e Pausa Lanche de 20 minutos.

Dentro dessas pausas, você pode usar o computador do jeito que você quiser.

Os Intervalos de 10 minutos são liberados a cada 1h20min de contrato ativo; as Pausas de 20 minutos são liberadas a cada 3h de trabalho. Eles continuam sendo liberados até você terminar todas as atividades e completar o dia.

## .: CRÉDITOS DE FLEXIBILIDADE :.

Créditos de flexibilidade são uma função nativa dentro do IRS para criar uma exceção para o dia de hoje. Nos dias que você avaliar não ser possível completar o tempo normal da atividade cadastrada — por exemplo, 90 minutos de escrita diariamente — você pode usar os créditos de flexibilidade.

A flexibilidade permite que todas as atividades do dia tenham o tempo reduzido para 15 minutos mínimos. Em dias de imprevistos, faça o mínimo e finalize o dia. Sem quebrar sua sequência.

## .: RECARGAS E MÉRITOS :.

Todo início de mês, o sistema completa seu estoque para 2 créditos mínimos. Mas você pode ganhar mais créditos flex completando 10 dias seguidos de tarefas (streak). Ao fazer isso, você ganha um Mérito (+1 crédito flex), podendo acumular até 4 no total.

## .: PASSES LIVRES :.

Quando você já tem 4 créditos e completa mais um streak de 10 dias, você ganha um crédito Trigger, possibilitando a troca desses 4 créditos por um Passe Livre.

O Passe Livre te permite folgar o dia inteiro sem precisar fazer nada. Enquanto os créditos flex expiram em 90 dias, os Passes não expiram nunca.

## .: BANCO DE HORAS :.

Ao cadastrar o tempo mínimo em uma atividade no IRS, todo tempo extra trabalhado é registrado no Banco de Horas.

As horas extras entram no banco de forma bloqueada e ficam disponíveis após 6 meses da data de registro.

Quando houver tempo liberado, elas só podem ser usadas via Contrato de Silêncio, descontando diretamente do banco. Assim, para dias de baixa energia, você pode usar seu computador do jeito que quiser... descontando tempo do banco. Depois, faz as atividades do dia.

O banco de horas não substitui a flexibilidade e os passes livres; além disso, não cobre falhas — você ainda precisa completar as atividades do dia.

O Banco registra apenas o tempo excedente até o dobro do tempo mínimo da atividade. Exemplo: se o mínimo é 2h, trabalhar 3h gera 1h de banco; trabalhar 4h gera 2h de banco. Trabalhar 5h também gera apenas 2h de banco. Essa regra mantém os incentivos corretos no uso do IRS.

Com o banco de horas, você também pode trocar tempo por passes livres. 24 horas trocam 1 passe livre.

---

# 📂 Arquitetura do Sistema

## identidade_rejeitada.py

Faz o setup do sistema para iniciar automaticamente junto com o Windows em dois modos: Daemon e Interface Gráfica. Ele também seta para o modo Daemon um watchdog com o arquivo logic.py no agendador de tarefas para verificar a cada 5 minutos se o aplicativo está sendo executado.

## logic.py

Faz a verificação se o Daemon continua rodando em background no computador. Caso contrário, ele faz a execução do arquivo do IRS novamente. Ele faz um registro no log de segurança para dois eventos: O primeiro é caso o Daemon não esteja rodando, porém o computador acabou de ser ligado. Nesse caso, ele inicia o Daemon silenciosamente. O segundo caso é quando o Daemon já foi rodado e por algum motivo não está mais presente na lista de processos. É feito o registro de sabotagem e o Daemon é reiniciado silenciosamente.

## daemon.py

Esse arquivo faz quase todas as operações importantes do IRS em várias funções:

### FocusCheckSession

Ao iniciar o computador pela primeira vez, ele pede para você confirmar se você quer descansar ou começar a trabalhar. Caso escolha descansar, ele desliga o computador. Caso escolha trabalhar, ele confirma o uso do computador com uma tela de motivação.

### PsychologicalSession

Caso o watchdog registre que o aplicativo foi fechado manualmente, ou seja, sofreu uma sabotagem, uma tela com uma mensagem será exibida para o usuário para fazer um realinhamento de expectativas quanto ao IRS.

### YellowAlertManager

Janela que é exibida para tarefas com horário fixo para começar. Essa janela fica fixada no canto direito do monitor e exibe a mensagem de que você deve imediatamente iniciar a tarefa marcada. Caso contrário, o computador será desligado em algum momento entre 2 a 15 minutos após a mensagem aparecer.

### IdentityRejectionSystem

O responsável por rodar as rejeições, as frases cadastradas no Gerenciador de Rejeições na interface gráfica. Caso tenha atividades para hoje, ele exibe rejeições. Caso o contrato de silêncio esteja ativado, todas as tarefas estejam cumpridas ou não tenha tarefas para hoje, ele não exibe rejeições.

Quando uma rejeição é tocada, são mostradas três popups com três rejeições diferentes em sequência, podendo mudar o local da tela onde aparecem. Além disso, para cada rejeição, o volume do computador é setado para 100.

Ao iniciar o computador, o IRS disponibiliza um Grace Period, um tempo aleatório de 15 a 30 minutos onde não é tocada nenhuma rejeição. Após esse período acabar, as rejeições já começam a tocar automaticamente entre 1 a 3 minutos.

Os popups têm dois modos de exibição: o primeiro é o popup padrão com tamanho de 500x200; o segundo é o modo severe, que é exibido ocupando 80% da tela. O segundo modo é exibido quando se passa 15 minutos após o Grace Period sem ativar nenhum contrato.

## core.py

Armazena todas as funções importantes de lógica do funcionamento do aplicativo. Como o sistema de escrita de arquivos usando temp_file. A configuração de todos os LOGs de configuração, segurança, integridade e histórico. O sistema de backup para o AppData. A verificação de integridade da blockchain dos logs.

Os logs History e Security funcionam como uma blockchain. Cada registro é assinado com o hash do bloco anterior para impedir alterações.

## bank_manager.py

Gerencia os registros de horas extras no banco de horas do aplicativo. Ele também verifica a integridade do log History, exibe alertas de segurança caso encontre violações, faz auditorias, adiciona novos blocos e cria a lógica de gasto de tempo.

## gui.py

Toda a configuração da interface gráfica do aplicativo.

### Página Inicial

Exibe uma barra de progresso do ano atual, onde você vê a data de hoje e a porcentagem do ano que já passou. Ele é atualizado automaticamente.

O checkbox "Modo Estudo/Trabalho" carrega o Contrato de Silêncio para iniciar suas atividades.

O botão "Menu" irá exibir as funções: Gerenciador de Tarefas, Loja da Disciplina, Banco de Horas, Gerenciador de Rejeições, Configurar Velocidade e Testar Áudio.

Abaixo de "Tarefas de Rotina" são exibidas as atividades do dia de hoje, exibindo um checkbox para cada atividade. Quando você quiser completar, clique no checkbox; uma janela irá abrir para detalhar o tempo que você ficou na atividade e também um resumo ou imagem como prova.

### Gerenciador de Tarefas

Nessa janela é possível ver todas as atividades cadastradas. Você pode selecionar uma atividade para Editar, criar uma Nova Tarefa e também Ver tarefas arquivadas.

#### Nova Tarefa

Nessa janela, você irá configurar o Nome da Tarefa e o tempo mínimo, que pode ser configurado em minutos (90 minutos) ou horas (2 horas). Ao configurar o tempo mínimo, essa opção só pode ser alterada depois de 7 dias. O tempo mínimo é opcional.

A atividade pode ser configurada para iniciar em horário fixo HH:MM (14:30).

A Frequência também pode ser configurada para a atividade, definindo se ela irá ser feita todos os dias ou em dias específicos da semana.

A opção Arquivar inativa a tarefa.

#### Ver Arquivados

Nessa janela é possível ver todas as tarefas arquivadas e é possível Restaurá-las caso necessário.

### Loja da Disciplina

Nessa janela, ele exibirá os seus recursos disponíveis: seus Créditos, Passes e o Streak atual.

Abaixo é exibida a validade dos créditos e o botão "USAR FLEXIBILIDADE". Ao usar uma flexibilidade, o tempo mínimo de todas as atividades de hoje é configurado para 15 minutos. Ao usar uma flexibilidade, ele pausa o Streak e não gera banco com o tempo mínimo.

### Banco de Horas

Será exibido todo o tempo "A Liberar" e o tempo "Disponível" para você usar do jeito que quiser. A janela também exibirá uma tabela com todos os registros de cada hora extra que você fez.

### Gerenciador de Rejeições

Você pode configurar rejeições personalizadas. Ao abrir o app, ele já configura rejeições padrões. Aqui você pode remover ou adicionar novas.

### Configurar Velocidade & Testar Áudio

É possível configurar a velocidade com a qual as rejeições são lidas e também testar se o áudio está funcionando corretamente no seu computador. As rejeições não geram áudios, usam o sistema de acessibilidade do Windows.

## study_mode.py

Esse arquivo é responsável pelo Contrato de Silêncio. Uma janela exibe um menu com 2 opções: 30 e 60 minutos, para você escolher qual contrato quer ativar agora.

Abaixo, você deve escrever exatamente o que você fará dentro desse contrato, a atividade específica que você vai fazer.

Abaixo, ele também terá os botões de Intervalo 10 e Pausa 20, mostrando também o tempo total de contrato ativo e quanto falta para cada pausa, além de quantas você pode usar.

Quando estiver disponível, o Intervalo 10 fica com o botão ativo azul e a Pausa 20 fica ativa e verde.

Com tudo pronto, basta clicar em Assinar e Iniciar.

O contrato irá fiscalizar você de 3 a 4 vezes em algum tempo aleatório para verificar se você realmente está cumprindo com o combinado.

Ao iniciar o contrato, ele irá ficar com um overlay na tela, no canto inferior esquerdo, com "CONTRATO ATIVO" em vermelho desfocado e a atividade que você especificou, até que o tempo encerre ou você feche manualmente.

---

# ⚠️ Ponto Importante...

As rejeições **NÃO** ficam tocando toda hora no seu computador.

Elas tocam apenas se:
- Você tiver atividades a serem feitas E não está com nenhum Contrato de Silêncio ativo.

Se:
- Não tem atividades;
- OU Você terminou todas as do dia.

**Pronto! Acabou por hoje.**

---


# 🛠️ Tecnologias Utilizadas

- Python 3.x (Lógica principal)
- Tkinter (Interface e Popups de interdição)
- PowerShell/TTS (Voz de Acessibilidade do sistema)
- SHA-256 (Segurança da Blockchain de horas e integridade de dados)
- Winreg/Schtasks (Persistência no Windows)

---

Ainda em desenvolvimento a partir da própria vivência do autor.
