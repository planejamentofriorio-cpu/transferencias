import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import extras
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import traceback

CRED_OP = {
    'host': 'aws-0-sa-east-1.pooler.supabase.com',
    'port': '6543',
    'dbname': 'postgres',
    'user': 'postgres.feaibbzfhvcllucprvvc',
    'password': 'CliffBurton1982!',
    'connect_timeout': 5
}

CRED_PLAN = {
    'host': 'aws-0-sa-east-1.pooler.supabase.com',
    'port': '6543',
    'dbname': 'postgres',
    'user': 'postgres.feaibbzfhvcllucprvvc',
    'password': 'CliffBurton1982!',
    'connect_timeout': 5
}

SMTP_SERVER = 'smtp.office365.com'  
SMTP_PORT = 587
SMTP_USER = 'luis.bedeschi@friorio.com.br' 
SMTP_PASSWORD = 'Cliffburton1982!'

EMAIL_PLANEJAMENTO = 'planejamento@friorio.com.br'
EMAIL_COMPRAS      = 'conrado@friorio.com.br'  
EMAIL_TRANSPORTES  = ['bruna.nogueira@friorio.com.br', 'rubens.souza@friorio.com.br']

MAP_EMAILS_CDS = {
    '01 - Serra': ['ronaldo.pereira@friorio.com.br', 'thuane.rodrigues@friorio.com.br', 'planejamento@friorio.com.br'],       
    '03 - Blumenau': ['rafael.vieira@friorio.com.br', 'vinicius.damasio@friorio.com.br', 'joanna.ercolin@friorio.com.br'],    
    '06 - São Paulo': ['fernando.brito@friorio.com.br', 'fabian.nahuel@friorio.com.br', 'planejamento@friorio.com.br']    
}

TODOS_ENVOLVIDOS = [EMAIL_PLANEJAMENTO, EMAIL_COMPRAS]
if isinstance(EMAIL_TRANSPORTES, list):
    TODOS_ENVOLVIDOS.extend(EMAIL_TRANSPORTES)
else:
    TODOS_ENVOLVIDOS.append(EMAIL_TRANSPORTES)

for lista_cd in MAP_EMAILS_CDS.values():
    if isinstance(lista_cd, list):
        TODOS_ENVOLVIDOS.extend(lista_cd)
    else:
        TODOS_ENVOLVIDOS.append(lista_cd)

TODOS_ENVOLVIDOS = list(set([e.strip() for e in TODOS_ENVOLVIDOS if isinstance(e, str) and e.strip()]))

st.set_page_config(page_title='FrioRio - Fluxo de Transferências Inter-CD', layout='wide')

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'erro_email' not in st.session_state:
    st.session_state.erro_email = None
if 'carrinho_compras' not in st.session_state:
    st.session_state.carrinho_compras = []

def get_conn(cred):
    return psycopg2.connect(**cred)

def inicializar_banco_notas():
    try:
        with get_conn(CRED_OP) as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS transferencia_notas_separacao (
                        id_separacao SERIAL PRIMARY KEY,
                        id_solicitacao INT NOT NULL REFERENCES solicitacoes_transferencia(id_solicitacao) ON DELETE CASCADE,
                        nota_fiscal VARCHAR(100) NOT NULL,
                        quantidade_separada INT NOT NULL,
                        volumetria_carga INT DEFAULT 1,
                        quantidade_recebida INT DEFAULT 0,
                        status_etapa VARCHAR(50) DEFAULT 'Pronto para Transporte',
                        transportadora VARCHAR(150),
                        data_separacao TIMESTAMP DEFAULT NOW(),
                        data_recebimento TIMESTAMP,
                        observacao TEXT
                    );
                ''')
                cur.execute('''
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transferencia_notas_separacao' and column_name='volumetria_carga') THEN
                            ALTER TABLE transferencia_notas_separacao ADD COLUMN volumetria_carga INT DEFAULT 1;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transferencia_notas_separacao' and column_name='quantidade_recebida') THEN
                            ALTER TABLE transferencia_notas_separacao ADD COLUMN quantidade_recebida INT DEFAULT 0;
                        END IF;
                    END $$;
                ''')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_transf_notas_solic ON transferencia_notas_separacao(id_solicitacao);')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_transf_notas_nf ON transferencia_notas_separacao(nota_fiscal);')
            conn.commit()
    except Exception as e:
        print('Erro ao inicializar tabela de notas: ' + str(e))

inicializar_banco_notas()

def obter_emails_destinatarios(cd_nome):
    if not cd_nome:
        return [EMAIL_PLANEJAMENTO]
    if cd_nome in MAP_EMAILS_CDS:
        return MAP_EMAILS_CDS[cd_nome]
    for chave, emails in MAP_EMAILS_CDS.items():
        if chave in str(cd_nome):
            return emails
    return [EMAIL_PLANEJAMENTO]

def disparar_email(destinatarios, assunto, corpo_texto):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        
        lista_envio = []
        def extrair_emails(item):
            if isinstance(item, str):
                if item.strip():
                    lista_envio.append(item.strip())
            elif isinstance(item, (list, tuple, set)):
                for subitem in item:
                    extrair_emails(subitem)

        extrair_emails(destinatarios)
        lista_envio = list(set(lista_envio))

        if not lista_envio:
            st.error('⚠️ Nenhum e-mail de destino válido foi informado.')
            return False

        msg['To'] = ', '.join(lista_envio)
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_texto, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, lista_envio, msg.as_string())
        return True
    except Exception as e:
        st.error('❌ Falha ao enviar e-mail: ' + str(e))
        st.session_state.erro_email = {
            'mensagem': type(e).__name__ + ': ' + str(e), 
            'traceback': traceback.format_exc()
        }
        return False

def email_modulo_1_multi(id_ordem, resumo_texto, rota, total_itens):
    assunto = '🟡 Módulo 1: Nova Solicitação de Ordem de Carga Multi-Itens #' + str(id_ordem)
    corpo = 'Nova Demanda de Transferencia Criada\n\nO setor de Compras inseriu uma nova ordem de carga.\n- ID de Controle: #' + str(id_ordem) + '\n- Rota Comercial: ' + str(rota) + '\n- Total de Itens: ' + str(total_itens) + '\n\nItens Solicitados:\n' + str(resumo_texto)
    disparar_email(EMAIL_PLANEJAMENTO, assunto, corpo)

def email_item_revisado_planejamento(id_solic, produto, rota, nova_qtd, justificativa):
    assunto = '🔄 Item #' + str(id_solic) + ' REVISADO por Compras'
    corpo = 'Item Recusado Corrigido\n\nO comprador revisou os parametros do item abaixo:\n- ID da Solicitacao: #' + str(id_solic) + '\n- Produto: ' + str(produto) + '\n- Rota: ' + str(rota) + '\n- Nova Quantidade: ' + str(nova_qtd) + '\n- Justificativa: ' + str(justificativa)
    disparar_email(EMAIL_PLANEJAMENTO, assunto, corpo)

def email_lote_aprovados_planejamento(resumo_texto, total_itens, lista_emails_cds):
    assunto = '🟢 Módulo 2: ' + str(total_itens) + ' Item(ns) APROVADOS pelo Planejamento'
    corpo = 'Itens Liberados para Separacao\n\n' + str(resumo_texto)
    disparar_email([EMAIL_PLANEJAMENTO] + lista_emails_cds, assunto, corpo)

def email_lote_recusados_planejamento(resumo_texto, total_itens):
    assunto = '🔴 Módulo 2: ' + str(total_itens) + ' Item(ns) RECUSADOS pelo Planejamento'
    corpo = 'Solicitacoes de Transferencia Recusadas\n\n' + str(resumo_texto)
    disparar_email(EMAIL_COMPRAS, assunto, corpo)

def email_modulo_3_resumido(rota, nota_fiscal, volumetria_nota, total_itens, resumo_texto):
    assunto = '🔵 Módulo 3: Número do Pedido ' + str(nota_fiscal) + ' da Rota ' + str(rota) + ' Pronto para Cotação'
    corpo = 'Dados de Volumetria e Número do Pedido Disponíveis para Cotação\n\n- Rota: ' + str(rota) + '\n- Número do Pedido: ' + str(nota_fiscal) + '\n- Volumetria da Carga: ' + str(volumetria_nota) + ' volumes\n- Quantidade de Itens no Pedido: ' + str(total_itens) + '\n\nComposicao:\n' + str(resumo_texto)
    disparar_email(EMAIL_TRANSPORTES, assunto, corpo)

def email_modulo_4_resumido(rota, cd_destino, transportadora, data_prevista, nota_fiscal, volumetria_nota):
    email_destinatario = obter_emails_destinatarios(cd_destino)
    assunto = '🚀 Módulo 4: Pedido ' + str(nota_fiscal) + ' da Rota ' + str(rota) + ' Em Trânsito (Previsão: ' + data_prevista.strftime('%d/%m/%Y') + ')'
    corpo = 'Número do Pedido Despachado\n\nA carga referente ao Número do Pedido **' + str(nota_fiscal) + '** da rota **' + str(rota) + '** contendo **' + str(volumetria_nota) + ' volumes** foi despachada via **' + str(transportadora) + '**. Previsão de chegada ao CD: ' + data_prevista.strftime('%d/%m/%Y') + '.\n\nO pedido já está disponível no painel do CD de Destino para conferência.'
    disparar_email([EMAIL_PLANEJAMENTO] + email_destinatario, assunto, corpo)

def email_lote_concluido(nome_grupo, nota_fiscal, resumo_texto):
    assunto = '✅ RECEBIMENTO CONCLUÍDO: Número do Pedido ' + str(nota_fiscal) + ' — ' + str(nome_grupo)
    corpo = 'Conferencia de Número do Pedido Finalizada\n\nO CD deu entrada no Número do Pedido **' + str(nota_fiscal) + '** do lote: **' + str(nome_grupo) + '**.\n\nResumo:\n' + str(resumo_texto)
    disparar_email(TODOS_ENVOLVIDOS, assunto, corpo)

def email_transferencia_cancelada_planejamento(id_solic, produto, origem, destino, motivo):
    assunto = '❌ ALERTA: Transferência ID #' + str(id_solic) + ' Cancelada pelo Planejamento'
    corpo = 'Transferência Cancelada\n\nA solicitação abaixo foi cancelada pelo Planejamento:\n- ID da Solicitação: #' + str(id_solic) + '\n- Produto: ' + str(produto) + '\n- Rota: ' + str(origem) + ' ➔ ' + str(destino) + '\n- Motivo/Justificativa: ' + str(motivo)
    disparar_email(TODOS_ENVOLVIDOS, assunto, corpo)

if st.session_state.erro_email:
    with st.container(border=True):
        st.error('❌ Erro no envio de e-mail:')
        st.code(st.session_state.erro_email['mensagem'], language='text')
        if st.button('Limpar aviso de erro', use_container_width=True):
            st.session_state.erro_email = None
            st.rerun()

if not st.session_state.logado:
    st.title('🚚 Sistema de Transferências Entre CDs')
    with st.container(border=True):
        u = st.text_input('Usuário')
        s = st.text_input('Senha', type='password')
        if st.button('Acessar Sistema', use_container_width=True):
            try:
                with get_conn(CRED_OP) as conn:
                    with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                        cur.execute('SELECT nome, departamento, cd_responsavel FROM usuarios WHERE login = %s AND senha = %s', (u.strip(), s.strip()))
                        user = cur.fetchone()
                        if user:
                            st.session_state.logado = True
                            st.session_state.nome = user['nome']
                            st.session_state.depto = user['departamento']
                            st.session_state.cd_user = user['cd_responsavel']
                            st.rerun()
                        else:
                            st.error('Usuário ou senha inválidos.')
            except Exception as e:
                st.error('Erro de conexão: ' + str(e))

else:
    st.sidebar.title('FrioRio Distribuidora')
    st.sidebar.write('**Usuário:** ' + str(st.session_state.nome))
    st.sidebar.write('**Setor:** ' + str(st.session_state.depto))
    if st.session_state.cd_user:
        st.sidebar.write('**Unidade:** ' + str(st.session_state.cd_user))
    if st.sidebar.button('Sair'):
        st.session_state.logado = False
        st.session_state.carrinho_compras = []
        st.rerun()

    if st.session_state.depto in ['Compras', 'Master']:
        st.header('📦 Módulo de Compras - Ordem de Carga Multi-Produtos')
        tab_nova, tab_acompanhar = st.tabs(['🆕 Criar Ordem Multi-Itens', '🔍 Acompanhar e Corrigir'])
        
        try:
            with get_conn(CRED_PLAN) as conn_p:
                df_base = pd.read_sql('SELECT cod_produto, descricao FROM estoque_master', conn_p)
            df_base['display'] = df_base['cod_produto'].astype(str) + ' - ' + df_base['descricao']
        except Exception as e:
            st.error('Erro ao carregar estoque: ' + str(e))
            df_base = pd.DataFrame(columns=['cod_produto', 'descricao', 'display'])

        with tab_nova:
            st.subheader('1. Dados de Cabeçalho da Ordem')
            col_orig, col_dest = st.columns(2)
            lista_cds = ['01 - Serra', '03 - Blumenau', '06 - São Paulo']
            origem = col_orig.selectbox('CD Origem (Saindo de)', lista_cds, key='orig_multi')
            destino = col_dest.selectbox('CD Destino (Indo para)', lista_cds, key='dest_multi')
            
            st.markdown('---')
            col_manual, col_upload = st.columns([1, 1])
            
            with col_manual:
                st.subheader('2a. Adicionar Item Manual')
                with st.container(border=True):
                    prod_sel = st.selectbox('Selecione o Produto', df_base['display'], key='prod_multi')
                    col_qtd, col_un = st.columns(2)
                    vol = col_qtd.number_input('Quantidade', min_value=1, value=1, key='vol_multi')
                    u_med = col_un.selectbox('Unidade', ['UN', 'PC', 'CX', 'KG', 'MT', 'PCT'], key='un_multi')
                    ref = st.text_input('Referência Fabricante', key='ref_multi')
                    
                    if st.button('➕ Adicionar Produto à Lista', use_container_width=True):
                        if origem == destino:
                            st.error('O CD de Origem não pode ser idêntico ao CD de Destino.')
                        else:
                            cod_p = prod_sel.split(' - ')[0]
                            desc_p = ' - '.join(prod_sel.split(' - ')[1:])
                            st.session_state.carrinho_compras.append({
                                'cod_produto': cod_p, 'descricao': desc_p, 'unidade_medida': u_med,
                                'referencia_fabricante': ref, 'volume_solicitado': vol
                            })
                            st.toast('Item inserido na lista!')

            with col_upload:
                st.subheader('2b. Inclusão em Massa via Excel')
                with st.container(border=True):
                    st.markdown('Colunas exigidas: `Código do Produto`, `Descrição do Produto`, `Quantidade`, `Unidade de Medida`')
                    arquivo_excel = st.file_uploader('Selecione a planilha Excel', type=['xlsx', 'xls'])
                    
                    if st.button('📥 Importar Itens da Planilha', use_container_width=True):
                        if origem == destino:
                            st.error('O CD de Origem não pode ser idêntico ao CD de Destino.')
                        elif arquivo_excel is not None:
                            try:
                                df_importado = pd.read_excel(arquivo_excel)
                                colunas_obrigatorias = ['Código do Produto', 'Descrição do Produto', 'Quantidade', 'Unidade de Medida']
                                
                                if not all(col in df_importado.columns for col in colunas_obrigatorias):
                                    st.error('Erro no layout! Colunas obrigatórias ausentes.')
                                else:
                                    contador_lote = 0
                                    for _, linha in df_importado.iterrows():
                                        c_prod = str(linha['Código do Produto']).strip()
                                        d_prod = str(linha['Descrição do Produto']).strip()
                                        qtd_val = int(linha['Quantidade'])
                                        u_val = str(linha['Unidade de Medida']).strip()
                                        
                                        if c_prod and d_prod and qtd_val > 0:
                                            st.session_state.carrinho_compras.append({
                                                'cod_produto': c_prod, 'descricao': d_prod, 'unidade_medida': u_val if u_val else 'UN',
                                                'referencia_fabricante': '', 'volume_solicitado': qtd_val
                                            })
                                            contador_lote += 1
                                    st.success('Sucesso! ' + str(contador_lote) + ' itens importados.')
                                    st.rerun()
                            except Exception as ex_excel:
                                st.error('Erro ao processar Excel: ' + str(ex_excel))
                        else:
                            st.warning('Selecione um arquivo válido.')

            st.markdown('---')
            if st.session_state.carrinho_compras:
                st.markdown('### 🛒 Itens Prontos na Ordem Atual:')
                df_car = pd.DataFrame(st.session_state.carrinho_compras)
                st.dataframe(df_car, use_container_width=True)
                
                col_limp, col_gravar = st.columns(2)
                if col_limp.button('🗑️ Limpar Toda a Lista', use_container_width=True):
                    st.session_state.carrinho_compras = []
                    st.rerun()
                    
                if col_gravar.button('🚀 Confirmar e Enviar Ordem Unificada', type='primary', use_container_width=True):
                    try:
                        with get_conn(CRED_OP) as conn_op:
                            with conn_op.cursor() as cur:
                                ids_gerados = []
                                resumo_texto_email = ''
                                
                                for item in st.session_state.carrinho_compras:
                                    cur.execute('''
                                        INSERT INTO solicitacoes_transferencia 
                                        (cod_produto, descricao, unidade_medida, referencia_fabricante, cd_origem, cd_destino, volume_solicitado, status_atual, criado_por, data_criacao)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendente Aprovação', %s, NOW())
                                        RETURNING id_solicitacao
                                    ''', (item['cod_produto'], item['descricao'], item['unidade_medida'], item['referencia_fabricante'], origem, destino, item['volume_solicitado'], st.session_state.nome))
                                    id_item = cur.fetchone()[0]
                                    ids_gerados.append(id_item)
                                    resumo_texto_email += '- ID #' + str(id_item) + ': ' + str(item['cod_produto']) + ' - ' + str(item['descricao']) + ' (' + str(item['volume_solicitado']) + ' ' + str(item['unidade_medida']) + ')\n'
                                conn_op.commit()
                        
                        st.success('Ordem cadastrada com sucesso! IDs: ' + str(ids_gerados))
                        email_modulo_1_multi(ids_gerados[0], resumo_texto_email, origem + ' ➔ ' + destino, len(ids_gerados))
                        st.session_state.carrinho_compras = []
                        st.rerun()
                    except Exception as e:
                        st.error('Erro ao salvar ordem: ' + str(e))

        with tab_acompanhar:
            try:
                with get_conn(CRED_OP) as conn_op:
                    df_hist = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status_atual != 'CanceladoPlanejamento' ORDER BY id_solicitacao DESC", conn_op)
                
                if df_hist.empty:
                    st.info('Nenhum histórico encontrado.')
                else:
                    for idx, row in df_hist.iterrows():
                        status = row['status_atual']
                        id_sol = row['id_solicitacao']
                        
                        if status == 'Pendente Aprovação': badge = '🟡 Pendente'
                        elif status == 'Aprovado': badge = '🟢 Aprovado'
                        elif status == 'Recusado': badge = '🔴 Recusado'
                        elif status == 'Cancelado': badge = '⚪ Cancelado/Excluído'
                        else: badge = '🔵 ' + str(status)
                        
                        with st.expander(badge + ' | ID #' + str(id_sol) + ' - ' + str(row['descricao']) + ' (' + str(row['cd_origem']) + ' ➔ ' + str(row['cd_destino']) + ')'):
                            st.write('**Item:** ' + str(row['cod_produto']) + ' | **Quantidade:** ' + str(row['volume_solicitado']) + ' ' + str(row['unidade_medida']))
                            if row['justificativa_compras']:
                                st.info('💬 Última Justificativa: ' + str(row['justificativa_compras']))
                                
                            if status == 'Recusado':
                                st.error('❌ Motivo do Planejamento: ' + str(row['justificativa_recusa']))
                                col_form_edit, col_btn_del = st.columns([3, 1])
                                
                                with col_form_edit:
                                    with st.form('form_revisar_' + str(id_sol)):
                                        n_qtd = st.number_input('Nova Quantidade', min_value=1, value=int(row['volume_solicitado']), key='nqtd_' + str(id_sol))
                                        n_just = st.text_input('Justificativa da Correção', value='', key='njust_' + str(id_sol))
                                        
                                        if st.form_submit_button('🔄 Corrigir e Notificar Planejamento'):
                                            if n_just.strip() == '':
                                                st.error('Insira uma justificativa técnica.')
                                            else:
                                                with get_conn(CRED_OP) as conn_re:
                                                    with conn_re.cursor() as cur:
                                                        cur.execute('''
                                                            UPDATE solicitacoes_transferencia 
                                                            SET status_atual = 'Pendente Aprovação', volume_solicitado = %s,
                                                                justificativa_compras = %s, justificativa_recusa = NULL 
                                                            WHERE id_solicitacao = %s
                                                        ''', (n_qtd, n_just.strip(), id_sol))
                                                        conn_re.commit()
                                                st.success('Item devolvido para análise!')
                                                email_item_revisado_planejamento(id_sol, row['descricao'], row['cd_origem'] + ' -> ' + row['cd_destino'], n_qtd, n_just.strip())
                                                st.rerun()
                                                
                                with col_btn_del:
                                    if st.button('🗑️ Excluir', key='del_prod_' + str(id_sol), type='primary', use_container_width=True):
                                        with get_conn(CRED_OP) as conn_del:
                                            with conn_del.cursor() as cur:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'Cancelado' WHERE id_solicitacao = %s", (id_sol,))
                                                conn_del.commit()
                                        st.toast('Produto excluído!')
                                        st.rerun()
            except Exception as e:
                st.error('Erro ao monitorar itens: ' + str(e))

    elif st.session_state.depto == 'Planejamento':
        st.header('📊 Módulo de Planejamento - Avaliação de Demandas')
        tab_aprov, tab_cancelar = st.tabs(['📋 Aprovar Linhas (Lote)', '🗑️ Gerenciar e Cancelar Transferências'])
        
        with tab_aprov:
            try:
                with get_conn(CRED_OP) as conn_op:
                    df_sol = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status_atual = 'Pendente Aprovação' ORDER BY id_solicitacao ASC", conn_op)
                
                if df_sol.empty:
                    st.info('Nenhum item pendente de aprovação.')
                else:
                    st.subheader('Avaliação Individual de Itens via Checkbox')
                    with st.form('form_planejamento_lote_coletivo'):
                        lista_respostas_planejamento = []
                        
                        for idx, r in df_sol.iterrows():
                            id_sol = r['id_solicitacao']
                            with st.container(border=True):
                                st.markdown('**Item #' + str(id_sol) + '** — ' + str(r['cod_produto']) + ' - ' + str(r['descricao']))
                                st.write('**Rota:** ' + str(r['cd_origem']) + ' ➔ ' + str(r['cd_destino']) + ' | **Qtd:** ' + str(r['volume_solicitado']) + ' ' + str(r['unidade_medida']) + ' | **Solicitante:** ' + str(r['criado_por']))
                                
                                col_aprov, col_reprov, col_motivo = st.columns([1.5, 1.5, 5])
                                chk_aprovado = col_aprov.checkbox('🟢 Aprovar', key='chk_ap_' + str(id_sol))
                                chk_reprovado = col_reprov.checkbox('🔴 Reprovar', key='chk_rp_' + str(id_sol))
                                input_motivo = col_motivo.text_input('Motivo da recusa', value='', key='txt_mot_' + str(id_sol))
                                
                                lista_respostas_planejamento.append({
                                    'id_sol': id_sol, 'aprovado': chk_aprovado, 'reprovado': chk_reprovado, 'motivo': input_motivo, 'row': r
                                })
                        
                        btn_submeter_tudo = st.form_submit_button('💾 Finalizar Decisões do Lote', type='primary', use_container_width=True)
                        
                        if btn_submeter_tudo:
                            erros_v = False
                            lote_aprov = []
                            lote_rec = []
                            
                            for item in lista_respostas_planejamento:
                                if item['aprovado'] and item['reprovado']:
                                    st.error('Item #' + str(item['id_sol']) + ': Não selecione Aprovar e Reprovar juntos.')
                                    erros_v = True
                                if item['reprovado'] and item['motivo'].strip() == '':
                                    st.error('Item #' + str(item['id_sol']) + ': Informe o motivo da recusa.')
                                    erros_v = True
                                    
                                if not erros_v:
                                    if item['aprovado']:
                                        lote_aprov.append(item)
                                    elif item['reprovado']:
                                        lote_rec.append(item)
                                        
                            if not erros_v:
                                if not lote_aprov and not lote_rec:
                                    st.error('Nenhuma decisão marcada.')
                                else:
                                    with get_conn(CRED_OP) as conn_p:
                                        with conn_p.cursor() as cur:
                                            for item in lote_aprov:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'Aprovado', data_ultima_atualizacao = NOW() WHERE id_solicitacao = %s", (item['id_sol'],))
                                            for item in lote_rec:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'Recusado', justificativa_recusa = %s, data_ultima_atualizacao = NOW() WHERE id_solicitacao = %s", (item['motivo'].strip(), item['id_sol']))
                                        conn_p.commit()
                                    
                                    if lote_aprov:
                                        resumo_ap = ''
                                        emails_cds = []
                                        for item in lote_aprov:
                                            r = item['row']
                                            resumo_ap += '- ID #' + str(item['id_sol']) + ': ' + str(r['cod_produto']) + ' - ' + str(r['descricao']) + ' | Rota: ' + str(r['cd_origem']) + ' ➔ ' + str(r['cd_destino']) + ' | Qtd: ' + str(r['volume_solicitado']) + ' ' + str(r['unidade_medida']) + '\n'
                                            res_emails = obter_emails_destinatarios(r['cd_origem'])
                                            if isinstance(res_emails, list):
                                                emails_cds.extend(res_emails)
                                            else:
                                                emails_cds.append(res_emails)
                                        email_lote_aprovados_planejamento(resumo_ap, len(lote_aprov), list(set(emails_cds)))
                                        
                                    if lote_rec:
                                        resumo_rp = ''
                                        for item in lote_rec:
                                            r = item['row']
                                            resumo_rp += '- ID #' + str(item['id_sol']) + ': ' + str(r['cod_produto']) + ' - ' + str(r['descricao']) + ' | Rota: ' + str(r['cd_origem']) + ' ➔ ' + str(r['cd_destino']) + ' | Motivo: ' + str(item['motivo']) + '\n'
                                        email_lote_recusados_planejamento(resumo_rp, len(lote_rec))
                                        
                                    st.success('Lote processado com sucesso!')
                                    st.rerun()
            except Exception as e:
                st.error('Erro na aprovação: ' + str(e))

        with tab_cancelar:
            st.subheader('🗑️ Gestão e Cancelamento de Transferências (Exclusivo Planejamento)')
            st.markdown('Utilize os filtros abaixo para localizar e cancelar solicitações de transferência.')
            
            with st.form('form_filtros_cancelamento'):
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                filtro_id = col_f1.text_input('Filtrar por ID Exato')
                filtro_origem = col_f2.selectbox('CD Origem', ['Todos', '01 - Serra', '03 - Blumenau', '06 - São Paulo'])
                filtro_destino = col_f3.selectbox('CD Destino', ['Todos', '01 - Serra', '03 - Blumenau', '06 - São Paulo'])
                filtro_periodo = col_f4.date_input('Filtrar a partir da Data', value=None)
                
                btn_filtrar = st.form_submit_button('🔍 Buscar Transferências', use_container_width=True)

            try:
                with get_conn(CRED_OP) as conn_op:
                    query_busca = "SELECT * FROM solicitacoes_transferencia WHERE status_atual != 'CanceladoPlanejamento'"
                    params_busca = []
                    
                    if filtro_id.strip():
                        query_busca += " AND id_solicitacao = %s"
                        params_busca.append(int(filtro_id.strip()))
                    if filtro_origem != 'Todos':
                        query_busca += " AND cd_origem = %s"
                        params_busca.append(filtro_origem)
                    if filtro_destino != 'Todos':
                        query_busca += " AND cd_destino = %s"
                        params_busca.append(filtro_destino)
                    if filtro_periodo:
                        query_busca += " AND data_criacao >= %s"
                        params_busca.append(filtro_periodo)
                        
                    query_busca += " ORDER BY id_solicitacao DESC LIMIT 50"
                    df_busca = pd.read_sql(query_busca, conn_op, params=params_busca)
                
                if df_busca.empty:
                    st.info('Nenhuma transferência encontrada com os filtros informados.')
                else:
                    st.write(f'**Resultados encontrados ({len(df_busca)}):**')
                    for _, r in df_busca.iterrows():
                        id_s = r['id_solicitacao']
                        with st.container(border=True):
                            st.markdown(f'**ID #{id_s}** — Produto: `{r["cod_produto"]} - {r["descricao"]}` | Status Atual: `{r["status_atual"]}`')
                            st.write(f'**Rota:** {r["cd_origem"]} ➔ {r["cd_destino"]} | **Qtd:** {r["volume_solicitado"]} {r["unidade_medida"]} | **Criado por:** {r["criado_por"]}')
                            
                            with st.form(f'form_canc_id_{id_s}'):
                                motivo_canc = st.text_input('Motivo / Justificativa para o Cancelamento', key=f'motivo_c_{id_s}')
                                if st.form_submit_button('❌ Cancelar Definitivamente esta Transferência', type='primary'):
                                    if not motivo_canc.strip():
                                        st.error('Informe o motivo do cancelamento.')
                                    else:
                                        with get_conn(CRED_OP) as conn_upc:
                                            with conn_upc.cursor() as cur:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'CanceladoPlanejamento', justificativa_recusa = %s WHERE id_solicitacao = %s", (motivo_canc.strip(), id_s))
                                                conn_upc.commit()
                                        st.success(f'Transferência ID #{id_s} cancelada com sucesso!')
                                        email_transferencia_cancelada_planejamento(id_s, r['descricao'], r['cd_origem'], r['cd_destino'], motivo_canc.strip())
                                        st.rerun()
            except Exception as ex_busca:
                st.error('Erro ao buscar transferências: ' + str(ex_busca))

    elif st.session_state.depto == 'Transportes':
        st.header('🚛 Módulo de Cotação e Fretes')
        try:
            with get_conn(CRED_OP) as conn_op:
                df_tr = pd.read_sql('''
                    SELECT id_solicitacao, cod_produto, descricao, unidade_medida, cd_origem, cd_destino, volume_solicitado as quantidade_separada, status_atual 
                    FROM solicitacoes_transferencia 
                    WHERE status_atual = 'Pronto para Transporte'
                ''', conn_op)
                
                try:
                    df_notas = pd.read_sql("SELECT id_solicitacao, nota_fiscal, volumetria_carga, transportadora FROM transferencia_notas_separacao", conn_op)
                    if not df_tr.empty and not df_notas.empty:
                        df_tr = pd.merge(df_tr, df_notas, on='id_solicitacao', how='left')
                except:
                    pass
            
            if df_tr.empty:
                st.info('Sem pedidos aguardando despacho e cotação no momento.')
            else:
                if 'nota_fiscal' not in df_tr.columns:
                    df_tr['nota_fiscal'] = 'S/N'
                else:
                    df_tr['nota_fiscal'] = df_tr['nota_fiscal'].fillna('S/N')

                if 'volumetria_carga' not in df_tr.columns:
                    df_tr['volumetria_carga'] = 1
                else:
                    df_tr['volumetria_carga'] = df_tr['volumetria_carga'].fillna(1)

                st.subheader('Fila de Pedidos Prontos para Despacho e Atribuição de Transportadora')
                df_tr['chave_agrupamento'] = df_tr['cd_origem'].astype(str) + ' ➔ ' + df_tr['cd_destino'].astype(str) + ' (Pedido: ' + df_tr['nota_fiscal'].astype(str) + ')'
                
                for idx_g, nome_grupo in enumerate(df_tr['chave_agrupamento'].unique()):
                    df_sub_grupo = df_tr[df_tr['chave_agrupamento'] == nome_grupo]
                    
                    if df_sub_grupo.empty:
                        continue
                        
                    nota_atual = df_sub_grupo['nota_fiscal'].iloc[0]
                    vol_nota = int(df_sub_grupo['volumetria_carga'].iloc[0]) if pd.notna(df_sub_grupo['volumetria_carga'].iloc[0]) else 1
                    cd_dest_grupo = df_sub_grupo['cd_destino'].iloc[0]
                    ids_solic_lote = df_sub_grupo['id_solicitacao'].tolist()
                    
                    with st.container(border=True):
                        st.markdown('### 📦 Despacho do Pedido: ' + str(nome_grupo))
                        st.markdown('**Número do Pedido:** ' + str(nota_atual) + ' | **Volumetria da Carga:** **' + str(vol_nota) + ' volumes**')
                        
                        st.write('**Itens contemplados:**')
                        for _, row_item in df_sub_grupo.iterrows():
                            st.markdown('- ID #' + str(row_item['id_solicitacao']) + ': ' + str(row_item['cod_produto']) + ' - ' + str(row_item['descricao']) + ' (**' + str(row_item['quantidade_separada']) + ' ' + str(row_item['unidade_medida']) + '**)')
                        
                        with st.form('form_despacho_grupo_' + str(idx_g)):
                            col_t, col_d = st.columns(2)
                            transp = col_t.text_input('Transportadora cotada / Motorista', key='tname_g_' + str(idx_g))
                            dt_p = col_d.date_input('Previsão de Chegada ao CD Destino', key='dtp_g_' + str(idx_g))
                            
                            if st.form_submit_button('🚀 Salvar e Enviar Direto para o CD Destino', type='primary', use_container_width=True):
                                if not transp.strip():
                                    st.error('Informe a transportadora.')
                                else:
                                    with get_conn(CRED_OP) as conn_up:
                                        with conn_up.cursor() as cur:
                                            # Altera o status direto para 'Agendado' (liberando direto para o CD destino conferir)
                                            cur.execute('''
                                                UPDATE solicitacoes_transferencia 
                                                SET status_atual = 'Agendado'
                                                WHERE id_solicitacao = ANY(%s)
                                            ''', (ids_solic_lote,))
                                            
                                            try:
                                                cur.execute('''
                                                    UPDATE transferencia_notas_separacao 
                                                    SET transportadora = %s, status_etapa = 'Agendado', observacao = CONCAT(COALESCE(observacao, ''), ' | Previsão Chegada: ', %s)
                                                    WHERE id_solicitacao = ANY(%s)
                                                ''', (transp.strip(), str(dt_p), ids_solic_lote))
                                            except:
                                                pass

                                            conn_up.commit()
                                    
                                    st.success('Transportadora salva e pedido enviado diretamente para o CD de Destino!')
                                    email_modulo_4_resumido(nome_grupo, cd_dest_grupo, transp.strip(), dt_p, nota_atual, vol_nota)
                                    st.rerun()
        except Exception as e:
            st.error('Erro no módulo de transportes: ' + str(e))

    elif st.session_state.depto == 'CD':
        cd_logado = st.session_state.cd_user
        st.header('🏢 Painel Operacional - CD ' + str(cd_logado))
        tab_origem, tab_destino = st.tabs(['📤 Separação por Número do Pedido (Origem)', '📥 Conferência em Fases (Destino)'])
        
        with tab_origem:
            try:
                with get_conn(CRED_OP) as conn_op:
                    query = '''
                        SELECT s.id_solicitacao, s.cod_produto, s.descricao, s.volume_solicitado, s.unidade_medida, s.cd_origem, s.cd_destino, s.data_criacao,
                               COALESCE((SELECT SUM(quantidade_separada) FROM transferencia_notas_separacao WHERE id_solicitacao = s.id_solicitacao), 0) as total_ja_separado
                        FROM solicitacoes_transferencia s
                        WHERE s.status_atual = 'Aprovado' AND s.cd_origem = %s
                        ORDER BY s.data_criacao ASC, s.id_solicitacao ASC
                    '''
                    df_ori = pd.read_sql(query, conn_op, params=(cd_logado,))
                
                if not df_ori.empty:
                    df_ori['saldo_restante'] = df_ori['volume_solicitado'] - df_ori['total_ja_separado']
                    df_ori = df_ori[df_ori['saldo_restante'] > 0]

                if df_ori.empty:
                    st.info('Nenhum item pendente de separação na unidade ' + str(cd_logado) + '.')
                else:
                    st.subheader('Seleção de Itens e Atribuição do Número do Pedido')
                    with st.form('form_separacao_lote_nf'):
                        lista_inputs_sep = []
                        
                        for idx, row in df_ori.iterrows():
                            id_sol = row['id_solicitacao']
                            solicitado = int(row['volume_solicitado'])
                            ja_separado = int(row['total_ja_separado'])
                            saldo_restante = int(row['saldo_restante'])
                            
                            with st.container(border=True):
                                st.markdown('**Item #' + str(id_sol) + '** — ' + str(row['cod_produto']) + ' - ' + str(row['descricao']) + ' (' + str(row['cd_origem']) + ' ➔ ' + str(row['cd_destino']) + ')')
                                col_c1, col_c2, col_c3 = st.columns([2, 1.5, 2.5])
                                col_c1.write('Saldo Pendente: **' + str(saldo_restante) + ' / ' + str(solicitado) + ' ' + str(row['unidade_medida']) + '** (Já sep: ' + str(ja_separado) + ')')
                                
                                chk = col_c2.checkbox('Incluir neste Pedido', key='chk_incluir_' + str(id_sol))
                                qtd_sep = col_c3.number_input('Qtd a Separar', min_value=1, max_value=int(saldo_restante), value=int(saldo_restante), key='qtd_sep_lote_' + str(id_sol))
                                
                                lista_inputs_sep.append({
                                    'id_sol': id_sol, 'incluir': chk, 'quantidade': qtd_sep, 'saldo_restante': saldo_restante, 'row_dados': row
                                })
                        
                        st.markdown('---')
                        col_nf, col_vol = st.columns(2)
                        input_nf_lote = col_nf.text_input('Número do Pedido')
                        input_volumetria = col_vol.number_input('Volumetria da Carga (Total de Volumes do Pedido)', min_value=1, value=1)
                        
                        btn_gerar_nf = st.form_submit_button('📥 Finalizar e Despachar para o Transporte', type='primary', use_container_width=True)
                        
                        if btn_gerar_nf:
                            if not input_nf_lote.strip():
                                st.error('Informe o Número do Pedido.')
                            else:
                                itens_selecionados = [i for i in lista_inputs_sep if i['incluir'] and i['quantidade'] > 0]
                                if not itens_selecionados:
                                    st.error('Nenhum item foi selecionado com quantidade válida.')
                                else:
                                    resumo_detalhes_origem = ''
                                    cd_destino_geral = ''
                                    with get_conn(CRED_OP) as conn_ins:
                                        with conn_ins.cursor() as cur:
                                            for item in itens_selecionados:
                                                cur.execute('''
                                                    INSERT INTO transferencia_notas_separacao 
                                                    (id_solicitacao, nota_fiscal, quantidade_separada, volumetria_carga, status_etapa, data_separacao)
                                                    VALUES (%s, %s, %s, %s, 'Pronto para Transporte', NOW())
                                                ''', (item['id_sol'], input_nf_lote.strip(), item['quantidade'], int(input_volumetria)))
                                                
                                                cur.execute('''
                                                    UPDATE solicitacoes_transferencia 
                                                    SET status_atual = 'Pronto para Transporte'
                                                    WHERE id_solicitacao = %s
                                                ''', (item['id_sol'],))
                                                
                                                cd_destino_geral = item['row_dados']['cd_destino']
                                                resumo_detalhes_origem += '- ID #' + str(item['id_sol']) + ': ' + str(item['row_dados']['cod_produto']) + ' - ' + str(item['row_dados']['descricao']) + ' (' + str(item['quantidade']) + ' ' + str(item['row_dados']['unidade_medida']) + ')\n'
                                            conn_ins.commit()
                                    
                                    rota_completa = str(cd_logado) + ' ➔ ' + str(cd_destino_geral)
                                    email_modulo_3_resumido(rota_completa, input_nf_lote.strip(), int(input_volumetria), len(itens_selecionados), resumo_detalhes_origem)

                                    st.success('Número do Pedido ' + str(input_nf_lote.strip()) + ' gerado com sucesso, com ' + str(input_volumetria) + ' volume(s). E-mail enviado ao Transporte para cotação!')
                                    st.rerun()
            except Exception as e:
                st.error('Erro na origem do CD: ' + str(e))

        with tab_destino:
            try:
                with get_conn(CRED_OP) as conn_op:
                    query_dest = '''
                        SELECT s.id_solicitacao, s.cod_produto, s.descricao, s.cd_origem, s.cd_destino, s.unidade_medida, s.volume_solicitado as quantidade_separada, s.status_atual 
                        FROM solicitacoes_transferencia s
                        WHERE s.status_atual = 'Agendado' AND s.cd_destino = %s
                    '''
                    df_dest = pd.read_sql(query_dest, conn_op, params=(cd_logado,))
                    
                    try:
                        df_notas = pd.read_sql("SELECT id_solicitacao, nota_fiscal, volumetria_carga, transportadora, quantidade_recebida, observacao FROM transferencia_notas_separacao", conn_op)
                        if not df_dest.empty and not df_notas.empty:
                            df_dest = pd.merge(df_dest, df_notas, on='id_solicitacao', how='left', suffixes=('', '_nota'))
                    except:
                        pass
                
                if df_dest.empty:
                    st.info('Nenhuma carga em trânsito ou aguardando conferência no momento.')
                else:
                    if 'nota_fiscal' not in df_dest.columns:
                        df_dest['nota_fiscal'] = 'S/N'
                    else:
                        df_dest['nota_fiscal'] = df_dest['nota_fiscal'].fillna('S/N')

                    if 'volumetria_carga' not in df_dest.columns:
                        df_dest['volumetria_carga'] = 1
                    else:
                        df_dest['volumetria_carga'] = df_dest['volumetria_carga'].fillna(1)

                    if 'quantidade_recebida' not in df_dest.columns:
                        df_dest['quantidade_recebida'] = 0
                    else:
                        df_dest['quantidade_recebida'] = df_dest['quantidade_recebida'].fillna(0)

                    if 'transportadora' not in df_dest.columns:
                        df_dest['transportadora'] = 'Não informada'
                    else:
                        df_dest['transportadora'] = df_dest['transportadora'].fillna('Não informada')

                    st.subheader('Conferência Física em Fases por Número do Pedido')
                    df_dest['chave_grupo'] = df_dest['cd_origem'].astype(str) + ' ➔ ' + df_dest['cd_destino'].astype(str) + ' (Pedido: ' + df_dest['nota_fiscal'].astype(str) + ')'
                    
                    for idx_d, nome_grupo in enumerate(df_dest['chave_grupo'].unique()):
                        df_sub_dest = df_dest[df_dest['chave_grupo'] == nome_grupo]
                        
                        if df_sub_dest.empty:
                            continue
                            
                        nota_fiscal_atual = df_sub_dest['nota_fiscal'].iloc[0]
                        volumetria_atual = df_sub_dest['volumetria_carga'].iloc[0]
                        transp_atual = df_sub_dest['transportadora'].iloc[0]
                        obs_atual = df_sub_dest['observacao'].iloc[0] if 'observacao' in df_sub_dest.columns and pd.notna(df_sub_dest['observacao'].iloc[0]) else 'Sem observações'
                        
                        with st.container(border=True):
                            st.markdown('### 📥 Conferência de Carga: ' + str(nome_grupo))
                            st.caption('🚛 **Número do Pedido:** ' + str(nota_fiscal_atual) + ' | 📦 **Volumetria:** ' + str(volumetria_atual) + ' volumes | 🏢 **Transportadora:** ' + str(transp_atual))
                            st.text('Detalhes / Previsão: ' + str(obs_atual))
                            
                            with st.form('form_recebimento_fase_' + str(idx_d)):
                                lista_conf_inputs = []
                                
                                for _, r in df_sub_dest.iterrows():
                                    id_sep = r['id_solicitacao']
                                    id_solic = r['id_solicitacao']
                                    q_sep = int(r['quantidade_separada'])
                                    q_rec_anterior = int(r.get('quantidade_recebida', 0) if pd.notna(r.get('quantidade_recebida')) else 0)
                                    saldo_rec_pendente = max(0, q_sep - q_rec_anterior)
                                    
                                    st.markdown('**Item ID #' + str(id_solic) + '** — ' + str(r['cod_produto']) + ' - ' + str(r['descricao']))
                                    c1, c2, c3 = st.columns([4, 2, 2])
                                    c1.write('Separado no Pedido: **' + str(q_sep) + '** ' + str(r['unidade_medida']))
                                    
                                    chk_conf = c2.checkbox('Conferir', key='chk_fase_' + str(id_sep))
                                    q_recebe_agora = c3.number_input('Qtd Recebida Agora', min_value=0, max_value=int(q_sep), value=int(saldo_rec_pendente), key='qrec_fase_' + str(id_sep))
                                    
                                    lista_conf_inputs.append({
                                        'id_separacao': id_sep, 'id_sol': id_solic, 'conferido': chk_conf, 'qtd_recebida': q_recebe_agora, 'row': r
                                    })
                                    st.divider()
                                
                                chk_termo = st.checkbox('Confirmo a conferência física desta fase/pedido', key='termo_fase_' + str(idx_d))
                                
                                if st.form_submit_button('🏁 Finalizar Conferência', type='primary', use_container_width=True):
                                    if not chk_termo:
                                        st.error('É necessário marcar o termo de confirmação.')
                                    else:
                                        val_ok = True
                                        for item in lista_conf_inputs:
                                            if not item['conferido']:
                                                st.error('Confirme o item ID #' + str(item['id_sol']) + '.')
                                                val_ok = False
                                        
                                        if val_ok:
                                            resumo_email_rec = ''
                                            
                                            with get_conn(CRED_OP) as conn_rec:
                                                with conn_rec.cursor() as cur:
                                                    for item in lista_conf_inputs:
                                                        r_dados = item['row']
                                                        nova_qtd_rec = int(item['qtd_recebida'])
                                                        
                                                        try:
                                                            cur.execute('''
                                                                UPDATE transferencia_notas_separacao 
                                                                SET quantidade_recebida = COALESCE(quantidade_recebida, 0) + %s,
                                                                    status_etapa = CASE WHEN (COALESCE(quantidade_recebida, 0) + %s) >= quantidade_separada THEN 'Concluído' ELSE 'Separado Parcial' END,
                                                                    data_recebimento = NOW()
                                                                WHERE id_solicitacao = %s
                                                            ''', (nova_qtd_rec, nova_qtd_rec, item['id_sol']))
                                                        except:
                                                            pass
                                                        
                                                        cur.execute('''
                                                            UPDATE solicitacoes_transferencia 
                                                            SET status_atual = 'Concluído'
                                                            WHERE id_solicitacao = %s
                                                        ''', (item['id_sol'],))
                                                        
                                                        resumo_email_rec += '- ID #' + str(item['id_sol']) + ': ' + str(r_dados['cod_produto']) + ' - ' + str(r_dados['descricao']) + ' | Recebida: ' + str(nova_qtd_rec) + '\n'
                                                    conn_rec.commit()
                                            
                                            st.success('Recebimento registrado com sucesso!')
                                            email_lote_concluido(nome_grupo, nota_fiscal_atual, resumo_email_rec)
                                            st.rerun()
            except Exception as e:
                st.error('Erro no fechamento do CD destino: ' + str(e))
