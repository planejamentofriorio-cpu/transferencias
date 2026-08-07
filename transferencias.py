import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import extras
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import traceback

# --- CONFIGURAÇÕES DE ACESSO (SUPABASE TRANSACTION POOLER) ---
CRED_SUPABASE = {
    "host": "aws-0-sa-east-1.pooler.supabase.com",
    "port": "6543",
    "dbname": "postgres",
    "user": "postgres.feaibbzfhvcllucprvvc",
    "password": "CliffBurton1982!",
    "connect_timeout": 10
}

CRED_OP = CRED_SUPABASE
CRED_PLAN = CRED_SUPABASE

# --- CONFIGURAÇÃO DE E-MAIL (SMTP DE SAÍDA) ---
SMTP_SERVER = "smtp.office365.com"  
SMTP_PORT = 587
SMTP_USER = "luis.bedeschi@friorio.com.br" 
SMTP_PASSWORD = "Cliffburton1982!"

# --- MAPEAMENTO DINÂMICO DE E-MAILS POR SETOR / CD ---
EMAIL_PLANEJAMENTO = "planejamento@friorio.com.br"
EMAIL_COMPRAS      = "conrado@friorio.com.br"  
EMAIL_TRANSPORTES  = "bruna.nogueira@friorio.com.br"  

MAP_EMAILS_CDS = {
    "01 - Serra": "ronaldo.pereira@friorio.com.br",       
    "03 - Blumenau": "rafael.vieira@friorio.com.br",    
    "06 - São Paulo": "fernando.brito@friorio.com.br"    
}

TODOS_OS_EMAILS = [
    EMAIL_PLANEJAMENTO,
    EMAIL_COMPRAS,
    EMAIL_TRANSPORTES
] + list(MAP_EMAILS_CDS.values())

def enviar_email(destinatarios, assunto, corpo_html):
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    
    destinatarios = list(set([d for d in destinatarios if d]))
    
    if not destinatarios:
        return
        
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = ", ".join(destinatarios)
        msg["Subject"] = assunto

        msg.attach(MIMEText(corpo_html, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, destinatarios, msg.as_string())
        server.quit()
    except Exception as e:
        st.error(f"Erro ao enviar e-mail de notificação: {e}")

def get_conn(cred):
    return psycopg2.connect(**cred)

def autenticar_usuario(login, senha):
    try:
        with get_conn(CRED_OP) as conn:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, nome, login, departamento, email_pessoal, cd_responsavel 
                    FROM usuarios 
                    WHERE login = %s AND senha = %s AND ativo = TRUE
                """, (login, senha))
                user = cur.fetchone()
                return dict(user) if user else None
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def main():
    st.set_page_config(page_title="Sistema de Transferências inter-CDs", layout="wide")

    if 'usuario' not in st.session_state:
        st.session_state['usuario'] = None

    if st.session_state['usuario'] is None:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Login de Acesso")
            with st.form("form_login"):
                login_input = st.text_input("Usuário (Login)")
                senha_input = st.text_input("Senha", type="password")
                btn_login = st.form_submit_button("Entrar")
                
                if btn_login:
                    user = autenticar_usuario(login_input, senha_input)
                    if user:
                        st.session_state['usuario'] = user
                        st.success(f"Bem-vindo, {user['nome']}!")
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos, ou usuário inativo.")
        return

    user = st.session_state['usuario']
    st.sidebar.title(f"👤 {user['nome']}")
    st.sidebar.caption(f"Depto: {user['departamento']}")
    if st.sidebar.button("Sair (Logout)"):
        st.session_state['usuario'] = None
        st.rerun()

    st.sidebar.markdown("---")
    
    depto = user['departamento']
    opcoes_menu = []
    
    if depto in ['Compras', 'Admin']:
        opcoes_menu.append("Compras - Nova Solicitação")
    if depto in ['Planejamento', 'Admin']:
        opcoes_menu.append("Planejamento - Aprovação")
    if depto in ['Transportes', 'Admin']:
        opcoes_menu.append("Transportes - Cotação de Frete")
    if depto in ['CD', 'CD Origem', 'Admin']:
        opcoes_menu.append("CD Origem - Agendamento de Coleta")
    if depto in ['CD', 'CD Destino', 'Admin']:
        opcoes_menu.append("CD Destino - Agendamento de Recebimento")
    
    opcoes_menu.append("Histórico Geral")

    aba = st.sidebar.radio("Selecione a Etapa do Processo:", opcoes_menu)

    # ----------------------------------------------------
    # ABA 1: COMPRAS
    # ----------------------------------------------------
    if aba == "Compras - Nova Solicitação":
        st.header("🛒 Compras - Solicitação de Transferência inter-CDs")
        
        try:
            with get_conn(CRED_PLAN) as conn_p:
                df_base = pd.read_sql("SELECT cod_produto, descricao_produto AS descricao FROM estoque_master", conn_p)
            df_base['display'] = df_base['cod_produto'].astype(str) + " - " + df_base['descricao'].astype(str)
            
            with st.form("form_compras", clear_on_submit=True):
                st.subheader("1. Dados da Transferência")
                c1, c2 = st.columns(2)
                with c1:
                    cd_origem = st.selectbox("CD Origem (Expedição)", ["01 - Serra", "03 - Blumenau", "06 - São Paulo"])
                with c2:
                    cd_destino = st.selectbox("CD Destino (Recebimento)", ["01 - Serra", "03 - Blumenau", "06 - São Paulo"])
                
                data_limite = st.date_input("Data Limite para Chegada no Destino")
                tipo_frete = st.radio("Tipo de Frete Solicitado", ["FOB (Nosso Frete)", "CIF (Fornecedor)"], horizontal=True)
                
                st.subheader("2. Adicionar Itens à Solicitação")
                
                if 'itens_temp' not in st.session_state:
                    st.session_state.itens_temp = []

                prod_sel = st.selectbox("Buscar Produto (Código ou Descrição)", df_base['display'].tolist())
                qtd_sel = st.number_input("Quantidade a Transferir", min_value=1, value=1)
                
                c_add, c_clr = st.columns([1, 5])
                if c_add.form_submit_button("➕ Adicionar Item"):
                    cod = prod_sel.split(" - ")[0]
                    desc = " - ".join(prod_sel.split(" - ")[1:])
                    st.session_state.itens_temp.append({
                        "cod_produto": cod,
                        "descricao_produto": desc,
                        "quantidade": qtd_sel
                    })
                    st.rerun()

                if st.session_state.itens_temp:
                    st.write("**Itens Selecionados:**")
                    st.table(pd.DataFrame(st.session_state.itens_temp))
                    if st.form_submit_button("❌ Limpar Lista de Itens"):
                        st.session_state.itens_temp = []
                        st.rerun()

                st.subheader("3. Finalizar")
                obs = st.text_area("Observações para o Planejamento / Transportes")
                
                btn_finalizar = st.form_submit_button("🚀 Enviar Solicitação para o Planejamento")
                
                if btn_finalizar:
                    if cd_origem == cd_destino:
                        st.error("O CD de Origem não pode ser igual ao CD de Destino!")
                    elif not st.session_state.itens_temp:
                        st.error("Adicione pelo menos um item à transferência!")
                    else:
                        try:
                            with get_conn(CRED_OP) as conn_op:
                                with conn_op.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO solicitacoes_transferencia 
                                        (cd_origem, cd_destino, data_limite_chegada, tipo_frete, solicitante, status, observacoes_compras)
                                        VALUES (%s, %s, %s, %s, %s, 'AGUARDANDO APROVACAO PLANEJAMENTO', %s)
                                        RETURNING id_solicitacao
                                    """, (cd_origem, cd_destino, data_limite, tipo_frete, user['nome'], obs))
                                    
                                    id_sol = cur.fetchone()[0]
                                    
                                    for item in st.session_state.itens_temp:
                                        cur.execute("""
                                            INSERT INTO itens_solicitacao 
                                            (id_solicitacao, cod_produto, descricao_produto, quantidade_solicitada)
                                            VALUES (%s, %s, %s, %s)
                                        """, (id_sol, item['cod_produto'], item['descricao_produto'], item['quantidade']))
                                        
                                    conn_op.commit()

                            destinatarios_email = [EMAIL_PLANEJAMENTO, EMAIL_COMPRAS]
                            corpo_email = f"""
                            <h3>Nova Solicitação de Transferência Criada!</h3>
                            <p><b>ID da Solicitação:</b> #{id_sol}</p>
                            <p><b>Solicitante:</b> {user['nome']}</p>
                            <p><b>Origem:</b> {cd_origem} ➔ <b>Destino:</b> {cd_destino}</p>
                            <p><b>Data Limite:</b> {data_limite.strftime('%d/%m/%Y')}</p>
                            <p><b>Tipo de Frete:</b> {tipo_frete}</p>
                            <p><b>Status Atual:</b> AGUARDANDO APROVAÇÃO PLANEJAMENTO</p>
                            <br>
                            <p>Acesse o sistema para analisar e aprovar esta solicitação.</p>
                            """
                            enviar_email(destinatarios_email, f"🚀 Nova Solicitação de Transferência inter-CDs #{id_sol}", corpo_email)

                            st.success(f"Solicitação #{id_sol} enviada com sucesso ao Planejamento!")
                            st.session_state.itens_temp = []
                        except Exception as e:
                            st.error(f"Erro ao salvar no banco de dados: {e}")

        except Exception as e:
            st.error(f"Erro ao carregar dados do banco: {e}")

    # ----------------------------------------------------
    # ABA 2: PLANEJAMENTO
    # ----------------------------------------------------
    elif aba == "Planejamento - Aprovação":
        st.header("📊 Planejamento - Aprovação de Transferências")
        
        try:
            with get_conn(CRED_OP) as conn_op:
                df_sol = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status = 'AGUARDANDO APROVACAO PLANEJAMENTO' ORDER BY id_solicitacao DESC", conn_op)
            
            if df_sol.empty:
                st.info("Não há solicitações pendentes de aprovação pelo Planejamento no momento.")
            else:
                for _, row in df_sol.iterrows():
                    with st.expander(f"Solicitação #{row['id_solicitacao']} - De: {row['cd_origem']} Para: {row['cd_destino']} (Limite: {row['data_limite_chegada']})"):
                        st.write(f"**Solicitante:** {row['solicitante']} | **Tipo de Frete Solicitado:** {row['tipo_frete']}")
                        st.write(f"**Obs Compras:** {row['observacoes_compras']}")
                        
                        with get_conn(CRED_OP) as conn_i:
                            df_itens = pd.read_sql(f"SELECT cod_produto, descricao_produto, quantidade_solicitada FROM itens_solicitacao WHERE id_solicitacao = {row['id_solicitacao']}", conn_i)
                        st.dataframe(df_itens, use_container_width=True)
                        
                        st.markdown("---")
                        c_ap, c_rec = st.columns(2)
                        
                        with c_ap:
                            st.subheader("Aprovar Solicitação")
                            tipo_frete_def = st.radio(f"Confirmar Tipo de Frete (ID {row['id_solicitacao']})", ["FOB (Nosso Frete)", "CIF (Fornecedor)"], index=0 if row['tipo_frete']=="FOB (Nosso Frete)" else 1, key=f"tf_{row['id_solicitacao']}")
                            obs_plan = st.text_area(f"Observações do Planejamento (ID {row['id_solicitacao']})", key=f"obs_p_{row['id_solicitacao']}")
                            
                            if st.button(f"✅ Aprovar #{row['id_solicitacao']}", key=f"btn_ap_{row['id_solicitacao']}"):
                                try:
                                    novo_status = 'AGUARDANDO COTACAO FRETE' if tipo_frete_def == 'FOB (Nosso Frete)' else 'AGUARDANDO AGENDAMENTO ORIGEM'
                                    
                                    with get_conn(CRED_OP) as conn_processa:
                                        with conn_processa.cursor() as cur:
                                            cur.execute("""
                                                UPDATE solicitacoes_transferencia 
                                                SET status = %s, tipo_frete = %s, observacoes_planejamento = %s, aprovador_planejamento = %s
                                                WHERE id_solicitacao = %s
                                            """, (novo_status, tipo_frete_def, obs_plan, user['nome'], row['id_solicitacao']))
                                            conn_processa.commit()
                                    
                                    destinatarios_email = [EMAIL_PLANEJAMENTO, EMAIL_COMPRAS]
                                    if tipo_frete_def == 'FOB (Nosso Frete)':
                                        destinatarios_email.append(EMAIL_TRANSPORTES)
                                    else:
                                        destinatarios_email.append(MAP_EMAILS_CDS.get(row['cd_origem']))

                                    corpo_email = f"""
                                    <h3>Solicitação #{row['id_solicitacao']} APROVADA pelo Planejamento!</h3>
                                    <p><b>Aprovado por:</b> {user['nome']}</p>
                                    <p><b>Tipo de Frete Definido:</b> {tipo_frete_def}</p>
                                    <p><b>Novo Status:</b> {novo_status}</p>
                                    <p><b>Observações:</b> {obs_plan}</p>
                                    """
                                    enviar_email(destinatarios_email, f"✅ Solicitação #{row['id_solicitacao']} Aprovada pelo Planejamento", corpo_email)

                                    st.success(f"Solicitação #{row['id_solicitacao']} Aprovada!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao aprovar: {e}")

                        with c_rec:
                            st.subheader("Recusar Solicitação")
                            motivo_rec = st.text_area(f"Motivo da Recusa (ID {row['id_solicitacao']})", key=f"mot_{row['id_solicitacao']}")
                            if st.button(f"❌ Recusar #{row['id_solicitacao']}", key=f"btn_rec_{row['id_solicitacao']}"):
                                if not motivo_rec:
                                    st.error("Informe o motivo da recusa.")
                                else:
                                    try:
                                        with get_conn(CRED_OP) as conn_processa:
                                            with conn_processa.cursor() as cur:
                                                cur.execute("""
                                                    UPDATE solicitacoes_transferencia 
                                                    SET status = 'RECUSADO PLANEJAMENTO', observacoes_planejamento = %s, aprovador_planejamento = %s
                                                    WHERE id_solicitacao = %s
                                                """, (motivo_rec, user['nome'], row['id_solicitacao']))
                                                conn_processa.commit()

                                        destinatarios_email = [EMAIL_PLANEJAMENTO, EMAIL_COMPRAS]
                                        corpo_email = f"""
                                        <h3>Solicitação #{row['id_solicitacao']} RECUSADA pelo Planejamento!</h3>
                                        <p><b>Analisado por:</b> {user['nome']}</p>
                                        <p><b>Motivo da Recusa:</b> {motivo_rec}</p>
                                        """
                                        enviar_email(destinatarios_email, f"❌ Solicitação #{row['id_solicitacao']} Recusada", corpo_email)

                                        st.warning(f"Solicitação #{row['id_solicitacao']} Recusada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao recusar: {e}")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    # ----------------------------------------------------
    # ABA 3: TRANSPORTES
    # ----------------------------------------------------
    elif aba == "Transportes - Cotação de Frete":
        st.header("🚚 Transportes - Cotação e Inclusão de Fretes")
        try:
            with get_conn(CRED_OP) as conn_op:
                df_tr = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status = 'AGUARDANDO COTACAO FRETE' ORDER BY id_solicitacao DESC", conn_op)
            
            if df_tr.empty:
                st.info("Não há solicitações pendentes de cotação de frete no momento.")
            else:
                for _, row in df_tr.iterrows():
                    with st.expander(f"Solicitação #{row['id_solicitacao']} - {row['cd_origem']} ➔ {row['cd_destino']} (Limite: {row['data_limite_chegada']})"):
                        st.write(f"**Solicitante:** {row['solicitante']} | **Obs Planejamento:** {row['observacoes_planejamento']}")
                        
                        with get_conn(CRED_OP) as conn_i:
                            df_itens = pd.read_sql(f"SELECT cod_produto, descricao_produto, quantidade_solicitada FROM itens_solicitacao WHERE id_solicitacao = {row['id_solicitacao']}", conn_i)
                        st.dataframe(df_itens, use_container_width=True)
                        
                        with st.form(f"form_tr_{row['id_solicitacao']}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                transp = st.text_input("Transportadora Contratada")
                                valor_f = st.number_input("Valor do Frete (R$)", min_value=0.0, format="%.2f")
                            with c2:
                                data_col_prev = st.date_input("Previsão de Coleta na Origem")
                                data_ent_prev = st.date_input("Previsão de Entrega no Destino")
                            
                            obs_tr = st.text_area("Observações do Transportes")
                            btn_salvar_tr = st.form_submit_button("✅ Finalizar Cotação e Enviar p/ CD Origem")
                            
                            if btn_salvar_tr:
                                if not transp:
                                    st.error("Informe a transportadora.")
                                else:
                                    try:
                                        with get_conn(CRED_OP) as conn_up:
                                            with conn_up.cursor() as cur:
                                                cur.execute("""
                                                    UPDATE solicitacoes_transferencia 
                                                    SET status = 'AGUARDANDO AGENDAMENTO ORIGEM', transportadora = %s, valor_frete = %s,
                                                        data_coleta_prevista = %s, data_entrega_prevista = %s, observacoes_transportes = %s
                                                    WHERE id_solicitacao = %s
                                                """, (transp, valor_f, data_col_prev, data_ent_prev, obs_tr, row['id_solicitacao']))
                                                conn_up.commit()

                                        destinatarios_email = [
                                            EMAIL_PLANEJAMENTO, 
                                            EMAIL_TRANSPORTES, 
                                            MAP_EMAILS_CDS.get(row['cd_origem'])
                                        ]
                                        corpo_email = f"""
                                        <h3>Cotação de Frete Concluída - Solicitação #{row['id_solicitacao']}</h3>
                                        <p><b>Transportadora:</b> {transp}</p>
                                        <p><b>Valor do Frete:</b> R$ {valor_f:.2f}</p>
                                        <p><b>Prev. Coleta Origem:</b> {data_col_prev.strftime('%d/%m/%Y')}</p>
                                        <p><b>Prev. Entrega Destino:</b> {data_ent_prev.strftime('%d/%m/%Y')}</p>
                                        <p><b>Novo Status:</b> AGUARDANDO AGENDAMENTO ORIGEM</p>
                                        """
                                        enviar_email(destinatarios_email, f"🚚 Frete Cotado - Solicitação #{row['id_solicitacao']}", corpo_email)

                                        st.success("Dados de frete salvos e enviados ao CD Origem!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar: {e}")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    # ----------------------------------------------------
    # ABA 4: CD ORIGEM
    # ----------------------------------------------------
    elif aba == "CD Origem - Agendamento de Coleta":
        st.header("📦 CD Origem - Agendamento de Coleta / Separação")
        try:
            with get_conn(CRED_OP) as conn_op:
                query = """
                    SELECT id_solicitacao, cd_origem, cd_destino, data_limite_chegada, tipo_frete,
                           transportadora, data_coleta_prevista, observacoes_transportes
                    FROM solicitacoes_transferencia 
                    WHERE status = 'AGUARDANDO AGENDAMENTO ORIGEM'
                """
                if user['departamento'] == 'CD' and user['cd_responsavel']:
                    query += f" AND cd_origem = '{user['cd_responsavel']}'"
                query += " ORDER BY id_solicitacao DESC"
                
                df_cd_o = pd.read_sql(query, conn_op)
            
            if df_cd_o.empty:
                st.info("Não há coletas pendentes de agendamento para o seu CD no momento.")
            else:
                for _, row in df_cd_o.iterrows():
                    with st.expander(f"Solicitação #{row['id_solicitacao']} - CD Origem: {row['cd_origem']} ➔ Destino: {row['cd_destino']}"):
                        st.write(f"**Transportadora:** {row['transportadora']} | **Data Prevista Coleta:** {row['data_coleta_prevista']}")
                        
                        with get_conn(CRED_OP) as conn_i:
                            df_itens = pd.read_sql(f"SELECT cod_produto, descricao_produto, quantidade_solicitada FROM itens_solicitacao WHERE id_solicitacao = {row['id_solicitacao']}", conn_i)
                        st.dataframe(df_itens, use_container_width=True)
                        
                        with st.form(f"form_cdo_{row['id_solicitacao']}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                data_col_real = st.date_input("Data Confirmada da Coleta/Saída", key=f"dt_c_{row['id_solicitacao']}")
                                num_nf = st.text_input("Número da Nota Fiscal (NF-e)", key=f"nf_{row['id_solicitacao']}")
                            with c2:
                                obs_cdo = st.text_area("Observações do CD Origem", key=f"obs_cdo_{row['id_solicitacao']}")
                            
                            btn_conf_col = st.form_submit_button("📦 Confirmar Separação/Coleta e Liberar para Destino")
                            
                            if btn_conf_col:
                                if not num_nf:
                                    st.error("Informe o número da Nota Fiscal.")
                                else:
                                    try:
                                        with get_conn(CRED_OP) as conn_up:
                                            with conn_up.cursor() as cur:
                                                cur.execute("""
                                                    UPDATE solicitacoes_transferencia 
                                                    SET status = 'EM TRÂNSITO / AGUARDANDO DESTINO', data_coleta_real = %s,
                                                        numero_nota_fiscal = %s, observacoes_cd_origem = %s
                                                    WHERE id_solicitacao = %s
                                                """, (data_col_real, num_nf, obs_cdo, row['id_solicitacao']))
                                                conn_up.commit()

                                        destinatarios_email = [
                                            EMAIL_PLANEJAMENTO, 
                                            EMAIL_TRANSPORTES, 
                                            MAP_EMAILS_CDS.get(row['cd_destino'])
                                        ]
                                        corpo_email = f"""
                                        <h3>Carga Expedida - Solicitação #{row['id_solicitacao']}</h3>
                                        <p><b>CD Origem:</b> {row['cd_origem']}</p>
                                        <p><b>CD Destino:</b> {row['cd_destino']}</p>
                                        <p><b>Nota Fiscal:</b> {num_nf}</p>
                                        <p><b>Data de Saída:</b> {data_col_real.strftime('%d/%m/%Y')}</p>
                                        <p><b>Novo Status:</b> EM TRÂNSITO / AGUARDANDO DESTINO</p>
                                        """
                                        enviar_email(destinatarios_email, f"📦 Carga em Trânsito (NF {num_nf}) - Solicitação #{row['id_solicitacao']}", corpo_email)

                                        st.success("Coleta e expedição confirmadas!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao atualizar: {e}")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    # ----------------------------------------------------
    # ABA 5: CD DESTINO
    # ----------------------------------------------------
    elif aba == "CD Destino - Agendamento de Recebimento":
        st.header("📥 CD Destino - Confirmação de Recebimento")
        try:
            with get_conn(CRED_OP) as conn_op:
                query = """
                    SELECT id_solicitacao, cd_origem, cd_destino, transportadora, numero_nota_fiscal, data_coleta_real
                    FROM solicitacoes_transferencia 
                    WHERE status = 'EM TRÂNSITO / AGUARDANDO DESTINO'
                """
                if user['departamento'] == 'CD' and user['cd_responsavel']:
                    query += f" AND cd_destino = '{user['cd_responsavel']}'"
                query += " ORDER BY id_solicitacao DESC"
                
                df_cd_d = pd.read_sql(query, conn_op)
            
            if df_cd_d.empty:
                st.info("Não há cargas em trânsito para o seu CD no momento.")
            else:
                for _, row in df_cd_d.iterrows():
                    with st.expander(f"Solicitação #{row['id_solicitacao']} - NF: {row['numero_nota_fiscal']} (Origem: {row['cd_origem']})"):
                        st.write(f"**Transportadora:** {row['transportadora']} | **Data Saída Origem:** {row['data_coleta_real']}")
                        
                        with get_conn(CRED_OP) as conn_i:
                            df_itens = pd.read_sql(f"SELECT id_item, cod_produto, descricao_produto, quantidade_solicitada FROM itens_solicitacao WHERE id_solicitacao = {row['id_solicitacao']}", conn_i)
                        
                        with st.form(f"form_cdd_{row['id_solicitacao']}"):
                            st.subheader("Conferência de Recebimento")
                            data_rec = st.date_input("Data do Recebimento Real", key=f"dt_r_{row['id_solicitacao']}")
                            
                            st.write("**Confira as quantidades recebidas:**")
                            qtds_recebidas = {}
                            for _, item in df_itens.iterrows():
                                qtds_recebidas[item['id_item']] = st.number_input(
                                    f"Qtd Recebida - {item['cod_produto']} ({item['descricao_produto']}) [Solicitado: {item['quantidade_solicitada']}]",
                                    min_value=0,
                                    value=int(item['quantidade_solicitada']),
                                    key=f"item_rec_{item['id_item']}"
                                )
                            
                            obs_cdd = st.text_area("Observações/Avarias/Divergências no Recebimento", key=f"obs_cdd_{row['id_solicitacao']}")
                            btn_finalizar_rec = st.form_submit_button("🎉 Finalizar Recebimento e Concluir Processo")
                            
                            if btn_finalizar_rec:
                                try:
                                    with get_conn(CRED_OP) as conn_final:
                                        with conn_final.cursor() as cur:
                                            for id_item_val, qtd_r in qtds_recebidas.items():
                                                cur.execute("UPDATE itens_solicitacao SET quantidade_recebida = %s WHERE id_item = %s", (qtd_r, id_item_val))
                                            
                                            cur.execute("""
                                                UPDATE solicitacoes_transferencia 
                                                SET status = 'CONCLUIDO', data_entrega_real = %s, observacoes_cd_destino = %s
                                                WHERE id_solicitacao = %s
                                            """, (data_rec, obs_cdd, row['id_solicitacao']))
                                            conn_final.commit()

                                    destinatarios_email = [
                                        EMAIL_PLANEJAMENTO, 
                                        EMAIL_COMPRAS, 
                                        EMAIL_TRANSPORTES, 
                                        MAP_EMAILS_CDS.get(row['cd_origem']),
                                        MAP_EMAILS_CDS.get(row['cd_destino'])
                                    ]
                                    corpo_email = f"""
                                    <h3>🎉 Transferência Concluída - Solicitação #{row['id_solicitacao']}</h3>
                                    <p><b>CD Destino:</b> {row['cd_destino']}</p>
                                    <p><b>Nota Fiscal:</b> {row['numero_nota_fiscal']}</p>
                                    <p><b>Data Recebimento:</b> {data_rec.strftime('%d/%m/%Y')}</p>
                                    <p><b>Observações Recebimento:</b> {obs_cdd}</p>
                                    <p><b>Status Final:</b> CONCLUÍDO</p>
                                    """
                                    enviar_email(destinatarios_email, f"🎉 Transferência Concluída - Solicitação #{row['id_solicitacao']}", corpo_email)

                                    st.success("Recebimento concluído com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao finalizar: {e}")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    # ----------------------------------------------------
    # ABA 6: HISTÓRICO GERAL
    # ----------------------------------------------------
    elif aba == "Histórico Geral":
        st.header("📋 Histórico Geral de Solicitações")
        try:
            with get_conn(CRED_OP) as conn_op:
                df_hist = pd.read_sql("SELECT * FROM solicitacoes_transferencia ORDER BY id_solicitacao DESC", conn_op)
            
            if df_hist.empty:
                st.info("Nenhuma solicitação encontrada.")
            else:
                st.dataframe(df_hist, use_container_width=True)
                
                id_det = st.number_input("Digite o ID da solicitação para ver os detalhes/itens:", min_value=1, step=1)
                if id_det:
                    with get_conn(CRED_OP) as conn_det:
                        df_det = pd.read_sql(f"SELECT * FROM itens_solicitacao WHERE id_solicitacao = {id_det}", conn_det)
                    if not df_det.empty:
                        st.subheader(f"Itens da Solicitação #{id_det}")
                        st.dataframe(df_det, use_container_width=True)
                    else:
                        st.warning("Solicitação não encontrada ou sem itens.")
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")

if __name__ == '__main__':
    main()