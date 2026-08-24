import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import extras
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import traceback

# --- CONFIGURAÇÕES DE ACESSO ---
CRED_OP = {
    "host": "aws-0-sa-east-1.pooler.supabase.com",
    "port": "6543",
    "dbname": "postgres",
    "user": "postgres.feaibbzfhvcllucprvvc",
    "password": "CliffBurton1982!",
    "connect_timeout": 5
}

CRED_PLAN = {
    "host": "aws-0-sa-east-1.pooler.supabase.com",
    "port": "6543",
    "dbname": "postgres",
    "user": "postgres.feaibbzfhvcllucprvvc",
    "password": "CliffBurton1982!",
    "connect_timeout": 5
}

# --- CONFIGURAÇÃO DE E-MAIL (SMTP DE SAÍDA) ---
SMTP_SERVER = "smtp.office365.com"  
SMTP_PORT = 587
SMTP_USER = "luis.bedeschi@friorio.com.br" 
SMTP_PASSWORD = "Cliffburton1982!"

# --- MAPEAMENTO DINÂMICO DE E-MAILS COM REDUNDÂNCIA ---
EMAIL_PLANEJAMENTO = "planejamento@friorio.com.br"
EMAIL_COMPRAS      = "conrado@friorio.com.br"  
EMAIL_TRANSPORTES  = ["bruna.nogueira@friorio.com.br", "rubens.souza@friorio.com.br"]

MAP_EMAILS_CDS = {
    "01 - Serra": ["ronaldo.pereira@friorio.com.br", "thuane.rodrigues@friorio.com.br", "planejamento@friorio.com.br"],       
    "03 - Blumenau": ["rafael.vieira@friorio.com.br", "vinicius.damasio@friorio.com.br", "planejamento@friorio.com.br"],    
    "06 - São Paulo": ["fernando.brito@friorio.com.br", "fabian.nahuel@friorio.com.br", "planejamento@friorio.com.br"]    
}

# --- CONSOLIDAÇÃO CORRETA E SEM DUPLICATAS DA LISTA GERAL ---
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

# Remove duplicatas e garante apenas strings limpas
TODOS_ENVOLVIDOS = list(set([e.strip() for e in TODOS_ENVOLVIDOS if isinstance(e, str) and e.strip()]))

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="FrioRio - Fluxo de Transferências Inter-CD", layout="wide")

# Inicialização das variáveis de estado (Sessão)
if 'logado' not in st.session_state:
    st.session_state.logado = False
if "erro_email" not in st.session_state:
    st.session_state.erro_email = None
if "carrinho_compras" not in st.session_state:
    st.session_state.carrinho_compras = []

def get_conn(cred):
    return psycopg2.connect(**cred)

# Helper para garantir extração correta de e-mails dos CDs
def obter_emails_destinatarios(cd_nome):
    if not cd_nome:
        return [EMAIL_PLANEJAMENTO]
    
    if cd_nome in MAP_EMAILS_CDS:
        return MAP_EMAILS_CDS[cd_nome]
    
    for chave, emails in MAP_EMAILS_CDS.items():
        if chave in str(cd_nome):
            return emails
            
    return [EMAIL_PLANEJAMENTO]

# =============================================================================
# MOTOR DE DISPARO DE E-MAILS (CORRIGIDO PARA MÚLTIPLOS DESTINATÁRIOS)
# =============================================================================
def disparar_email(destinatarios, assunto, corpo_html):
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
            st.error("⚠️ Nenhum e-mail de destino válido foi informado.")
            return False

        msg['To'] = ", ".join(lista_envio)
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_html, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, lista_envio, msg.as_string())
            
        return True
    except Exception as e:
        st.error(f"❌ Falha ao enviar e-mail: {str(e)}")
        st.session_state.erro_email = {
            "mensagem": f"{type(e).__name__}: {str(e)}", 
            "traceback": traceback.format_exc()
        }
        return False

# =============================================================================
# GATILHOS DE E-MAIL
# =============================================================================
def email_modulo_1_multi(id_ordem, tabela_html, rota, total_itens):
    assunto = f"🟡 Módulo 1: Nova Solicitação de Ordem de Carga Multi-Itens #{id_ordem}"
    corpo = f"""
    <html><body>
        <h2>Nova Demanda de Transferência Criada (Agrupada)</h2>
        <p>O setor de Compras inseriu uma nova ordem de carga contendo múltiplos itens.</p>
        <ul>
            <li><b>ID de Controle de Origem:</b> #{id_ordem}</li>
            <li><b>Rota Comercial:</b> {rota}</li>
            <li><b>Total de Itens na Carga:</b> {total_itens}</li>
        </ul>
        <br><h3>Itens Solicitados:</h3>{tabela_html}
        <p><i>Ação necessária: Acessar o módulo de Planejamento para avaliar os itens.</i></p>
    </body></html>
    """
    disparar_email(EMAIL_PLANEJAMENTO, assunto, corpo)

def email_item_revisado_planejamento(id_solic, produto, rota, nova_qtd, justificativa):
    assunto = f"🔄 Item #{id_solic} REVISADO por Compras - Nova Análise Necessária"
    corpo = f"""
    <html><body>
        <h2>Item Recusado foi Corrigido por Compras</h2>
        <p>O comprador revisou os parâmetros do item abaixo e o devolveu para a fila de aprovação.</p>
        <ul>
            <li><b>ID da Solicitação:</b> #{id_solic}</li>
            <li><b>Produto:</b> {produto}</li>
            <li><b>Rota:</b> {rota}</li>
            <li><b>Nova Quantidade Solicitada:</b> {nova_qtd}</li>
            <li><b>Justificativa do Comprador:</b> {justificativa}</li>
        </ul>
        <p><i>Por favor, reavalie este item no painel do Módulo de Planejamento.</i></p>
    </body></html>
    """
    disparar_email(EMAIL_PLANEJAMENTO, assunto, corpo)

# CORRIGIDO: Agora recebe a lista de e-mails dos CDs envolvidos no lote aprovado
def email_lote_aprovados_planejamento(tabela_html, total_itens, lista_emails_cds):
    assunto = f"🟢 Módulo 2: {total_itens} Item(ns) de Transferência APROVADOS pelo Planejamento"
    corpo = f"""
    <html><body>
        <h2>Itens de Carga Liberados para Separação</h2>
        <p>O setor de Planejamento avaliou e aprovou os seguintes itens para movimentação entre as filiais.</p>
        <br>{tabela_html}
        <p><i>Ação necessária nos respectivos CDs de Origem: Iniciar os procedimentos de separação e cubagem no painel.</i></p>
    </body></html>
    """
    destinatarios = [EMAIL_PLANEJAMENTO] + lista_emails_cds
    disparar_email(destinatarios, assunto, corpo)

def email_lote_recusados_planejamento(tabela_html, total_itens):
    assunto = f"🔴 Módulo 2: {total_itens} Item(ns) de Transferência RECUSADOS pelo Planejamento"
    corpo = f"""
    <html><body>
        <h2 style="color: #d32f2f;">Solicitações de Transferência Recusadas</h2>
        <p>Os itens listados abaixo foram analisados e <b>recusados</b> pela gerência de Planejamento.</p>
        <br>{tabela_html}
        <p><i>Os itens retornaram para o painel de Compras para correção de quantidades ou exclusão definitiva.</i></p>
    </body></html>
    """
    disparar_email(EMAIL_COMPRAS, assunto, corpo)

def email_modulo_3_resumido(rota, dados_logisticos, total_itens):
    assunto = f"🔵 Módulo 3: Carga Consolidada Pronta para Transporte — Rota {rota}"
    corpo = f"""
    <html><body>
        <h2>Dados Macroscópicos de Volumetria Disponíveis</h2>
        <p>O CD de Origem finalizou a pesagem e cubagem de uma carga unificada.</p>
        <ul>
            <li><b>Rota de Movimentação:</b> {rota}</li>
            <li><b>Total de Itens Diferentes:</b> {total_itens}</li>
            <li><b>Soma Total de Volumes:</b> {dados_logisticos['qtd_vol']} cx / un</li>
            <li><b>Peso Bruto Consolidado:</b> {dados_logisticos['peso_bruto']} kg</li>
            <li><b>Cubagem Total do Lote:</b> {dados_logisticos['cubagem']} m³</li>
        </ul>
        <p><i>Ação necessária: Acessar o módulo de Transportes para vincular a transportadora e realizar o despacho rodoviário.</i></p>
    </body></html>
    """
    disparar_email(EMAIL_TRANSPORTES, assunto, corpo)

def email_modulo_4_resumido(rota, transportadora, data_prevista, total_itens):
    assunto = f"🚀 Módulo 4: Carga da Rota {rota} Em Trânsito"
    corpo = f"""<html><body><h2>Lote Despachado</h2><p>A carga consolidada da rota <b>{rota}</b> contendo {total_itens} item(ns) foi coletada e enviada via transportadora <b>{transportadora}</b>. Previsão de chegada: {data_prevista.strftime('%d/%m/%Y')}</p></body></html>"""
    disparar_email(EMAIL_PLANEJAMENTO, assunto, corpo)

def email_modulo_5_resumido(rota, cd_destino, data_agenda, hora_agenda, total_itens):
    email_destinatario = obter_emails_destinatarios(cd_destino)
    assunto = f"📅 Módulo 5: Recebimento de Lote Agendado — Rota {rota}"
    corpo = f"""<html><body><h2>Janela de Doca Marcada (Carga Consolidada)</h2><p>A carga da rota <b>{rota}</b> contendo {total_itens} produto(s) teve seu descarregamento agendado na filial de destino para o dia <b>{data_agenda.strftime('%d/%m/%Y')}</b> às <b>{hora_agenda}</b>.</p></body></html>"""
    disparar_email(email_destinatario, assunto, corpo)

def email_lote_concluido(nome_grupo, total_itens, html_tabela):
    assunto = f"✅ PROCESSO CONCLUÍDO: Lote de Transferência Recebido — {nome_grupo}"
    corpo = f"""
    <html><body>
        <h2>Fluxo Logístico de Transferência Finalizado</h2>
        <p>O CD de destino realizou a conferência física e encerrou o lote de transferência: <b>{nome_grupo}</b>.</p>
        <p><b>Total de Itens Avaliados:</b> {total_itens}</p>
        <br><h3>Resumo do Recebimento por Item:</h3>
        {html_tabela}
        <p><i>Os saldos sistêmicos foram atualizados com sucesso nas filiais correspondentes.</i></p>
    </body></html>
    """
    disparar_email(TODOS_ENVOLVIDOS, assunto, corpo)


# --- EXIBIÇÃO DE ERROS LOGÍSTICOS NO TOPO ---
if st.session_state.erro_email:
    with st.container(border=True):
        st.error("❌ Erro no envio da notificação por e-mail:")
        st.code(st.session_state.erro_email["mensagem"], language="text")
        if st.button("Limpar aviso de erro", use_container_width=True):
            st.session_state.erro_email = None
            st.rerun()

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("🚚 Sistema de Transferências Entre CDs")
    with st.container(border=True):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.button("Acessar Sistema", use_container_width=True):
            try:
                with get_conn(CRED_OP) as conn:
                    with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                        cur.execute("SELECT nome, departamento, cd_responsavel FROM usuarios WHERE login = %s AND senha = %s", (u.strip(), s.strip()))
                        user = cur.fetchone()
                        if user:
                            st.session_state.logado = True
                            st.session_state.nome = user['nome']
                            st.session_state.depto = user['departamento']
                            st.session_state.cd_user = user['cd_responsavel']
                            st.rerun()
                        else:
                            st.error("Usuário ou senha inválidos.")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")

# --- CONTEÚDO DO SISTEMA ---
else:
    st.sidebar.title("FrioRio Distribuidora")
    st.sidebar.write(f"**Usuário:** {st.session_state.nome}")
    st.sidebar.write(f"**Setor:** {st.session_state.depto}")
    if st.session_state.cd_user:
        st.sidebar.write(f"**Unidade:** {st.session_state.cd_user}")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.session_state.carrinho_compras = []
        st.rerun()

    # =========================================================================
    # MÓDULO DE COMPRAS 
    # =========================================================================
    if st.session_state.depto == "Compras":
        st.header("📦 Módulo de Compras - Ordem de Carga Multi-Produtos")
        tab_nova, tab_acompanhar = st.tabs(["🆕 Criar Ordem Multi-Itens", "🔍 Acompanhar e Corrigir"])
        
        try:
            with get_conn(CRED_PLAN) as conn_p:
                df_base = pd.read_sql("SELECT cod_produto, descricao FROM estoque_master", conn_p)
            df_base['display'] = df_base['cod_produto'].astype(str) + " - " + df_base['descricao']
        except Exception as e:
            st.error(f"Erro ao carregar estoque: {e}")
            df_base = pd.DataFrame(columns=['cod_produto', 'descricao', 'display'])

        with tab_nova:
            st.subheader("1. Dados de Cabeçalho da Ordem")
            col_orig, col_dest = st.columns(2)
            lista_cds = ["01 - Serra", "03 - Blumenau", "06 - São Paulo"]
            origem = col_orig.selectbox("CD Origem (Saindo de)", lista_cds, key="orig_multi")
            destino = col_dest.selectbox("CD Destino (Indo para)", lista_cds, key="dest_multi")
            
            st.markdown("---")
            col_manual, col_upload = st.columns([1, 1])
            
            with col_manual:
                st.subheader("2a. Adicionar Item Manual")
                with st.container(border=True):
                    prod_sel = st.selectbox("Selecione o Produto", df_base['display'], key="prod_multi")
                    col_qtd, col_un = st.columns(2)
                    vol = col_qtd.number_input("Quantidade", min_value=1, value=1, key="vol_multi")
                    u_med = col_un.selectbox("Unidade", ["UN", "PC", "CX", "KG", "MT", "PCT"], key="un_multi")
                    ref = st.text_input("Referência Fabricante", key="ref_multi")
                    
                    if st.button("➕ Adicionar Produto à Lista", use_container_width=True):
                        if origem == destino:
                            st.error("O CD de Origem não pode ser idêntico ao CD de Destino.")
                        else:
                            cod_p = prod_sel.split(" - ")[0]
                            desc_p = " - ".join(prod_sel.split(" - ")[1:])
                            st.session_state.carrinho_compras.append({
                                "cod_produto": cod_p, "descricao": desc_p, "unidade_medida": u_med,
                                "referencia_fabricante": ref, "volume_solicitado": vol
                            })
                            st.toast("Item inserido na lista!")

            with col_upload:
                st.subheader("2b. Inclusão em Massa via Excel")
                with st.container(border=True):
                    st.markdown("O arquivo deve conter as colunas exatas: `Código do Produto`, `Descrição do Produto`, `Quantidade`, `Unidade de Medida`")
                    arquivo_excel = st.file_uploader("Arraste ou selecione a planilha Excel", type=["xlsx", "xls"])
                    
                    if st.button("📥 Importar Itens da Planilha", use_container_width=True):
                        if origem == destino:
                            st.error("O CD de Origem não pode ser idêntico ao CD de Destino.")
                        elif arquivo_excel is not None:
                            try:
                                df_importado = pd.read_excel(arquivo_excel)
                                colunas_obrigatorias = ["Código do Produto", "Descrição do Produto", "Quantidade", "Unidade de Medida"]
                                
                                if not all(col in df_importado.columns for col in colunas_obrigatorias):
                                    st.error(f"Erro no layout! O arquivo precisa ter as colunas: {', '.join(colunas_obrigatorias)}")
                                else:
                                    contador_lote = 0
                                    for _, linha in df_importado.iterrows():
                                        c_prod = str(linha["Código do Produto"]).strip()
                                        d_prod = str(linha["Descrição do Produto"]).strip()
                                        qtd_val = int(linha["Quantidade"])
                                        u_val = str(linha["Unidade de Medida"]).strip()
                                        
                                        if c_prod and d_prod and qtd_val > 0:
                                            st.session_state.carrinho_compras.append({
                                                "cod_produto": c_prod, "descricao": d_prod, "unidade_medida": u_val if u_val else "UN",
                                                "referencia_fabricante": "", "volume_solicitado": qtd_val
                                            })
                                            contador_lote += 1
                                    st.success(f"Sucesso! {contador_lote} itens da planilha foram injetados no carrinho abaixo.")
                                    st.rerun()
                            except Exception as ex_excel:
                                st.error(f"Erro ao processar o arquivo Excel: {ex_excel}")
                        else:
                            st.warning("Por favor, selecione um arquivo Excel válido antes de clicar.")

            st.markdown("---")
            if st.session_state.carrinho_compras:
                st.markdown("### 🛒 Itens Prontos na Ordem Atual:")
                df_car = pd.DataFrame(st.session_state.carrinho_compras)
                st.dataframe(df_car, use_container_width=True)
                
                col_limp, col_gravar = st.columns(2)
                if col_limp.button("🗑️ Limpar Toda a Lista", use_container_width=True):
                    st.session_state.carrinho_compras = []
                    st.rerun()
                    
                if col_gravar.button("🚀 Confirmar e Enviar Ordem Unificada", type="primary", use_container_width=True):
                    try:
                        with get_conn(CRED_OP) as conn_op:
                            with conn_op.cursor() as cur:
                                ids_gerados = []
                                rows_html = ""
                                
                                for item in st.session_state.carrinho_compras:
                                    cur.execute("""
                                        INSERT INTO solicitacoes_transferencia 
                                        (cod_produto, descricao, unidade_medida, referencia_fabricante, cd_origem, cd_destino, volume_solicitado, status_atual, criado_por, data_criacao)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendente Aprovação', %s, NOW())
                                        RETURNING id_solicitacao
                                    """, (item['cod_produto'], item['descricao'], item['unidade_medida'], item['referencia_fabricante'], origem, destino, item['volume_solicitado'], st.session_state.nome))
                                    id_item = cur.fetchone()[0]
                                    ids_gerados.append(id_item)
                                    rows_html += f"<tr><td>#{id_item}</td><td>{item['cod_produto']} - {item['descricao']}</td><td>{item['volume_solicitado']} {item['unidade_medida']}</td></tr>"
                                conn_op.commit()
                        
                        st.success(f"Ordem de Carga cadastrada com sucesso! IDs: {ids_gerados}")
                        tabela_html = f"<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'><tr style='background-color:#f2f2f2;'><th>ID Registro</th><th>Produto</th><th>Quantidade</th></tr>{rows_html}</table>"
                        email_modulo_1_multi(ids_gerados[0], tabela_html, f"{origem} ➔ {destino}", len(ids_gerados))
                        st.session_state.carrinho_compras = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar ordem no banco: {e}")

        with tab_acompanhar:
            try:
                with get_conn(CRED_OP) as conn_op:
                    df_hist = pd.read_sql("SELECT * FROM solicitacoes_transferencia ORDER BY id_solicitacao DESC", conn_op)
                
                if df_hist.empty:
                    st.info("Nenhum histórico encontrado.")
                else:
                    for idx, row in df_hist.iterrows():
                        status = row['status_atual']
                        id_sol = row['id_solicitacao']
                        
                        if status == 'Pendente Aprovação': badge = "🟡 Pendente"
                        elif status == 'Aprovado': badge = "🟢 Aprovado"
                        elif status == 'Recusado': badge = "🔴 Recusado"
                        elif status == 'Cancelado': badge = "⚪ Cancelado/Excluído"
                        else: badge = f"🔵 {status}"
                        
                        with st.expander(f"{badge} | ID #{id_sol} - {row['descricao']} ({row['cd_origem']} ➔ {row['cd_destino']})"):
                            st.write(f"**Item:** {row['cod_produto']} | **Quantidade:** {row['volume_solicitado']} {row['unidade_medida']}")
                            if row['justificativa_compras']:
                                st.info(f"💬 Última Justificativa de Compras: {row['justificativa_compras']}")
                                
                            if status == 'Recusado':
                                st.error(f"❌ Motivo do Planejamento: {row['justificativa_recusa']}")
                                col_form_edit, col_btn_del = st.columns([3, 1])
                                
                                with col_form_edit:
                                    with st.form(f"form_revisar_{id_sol}"):
                                        n_qtd = st.number_input("Nova Quantidade", min_value=1, value=int(row['volume_solicitado']), key=f"nqtd_{id_sol}")
                                        n_just = st.text_input("Justificativa da Correção", value="", key=f"njust_{id_sol}")
                                        
                                        if st.form_submit_button("🔄 Corrigir e Notificar Planejamento"):
                                            if n_just.strip() == "":
                                                st.error("Insira uma justificativa técnica para a revisão.")
                                            else:
                                                with get_conn(CRED_OP) as conn_re:
                                                    with conn_re.cursor() as cur:
                                                        cur.execute("""
                                                            UPDATE solicitacoes_transferencia 
                                                            SET status_atual = 'Pendente Aprovação', volume_solicitado = %s,
                                                                justificativa_compras = %s, justificativa_recusa = NULL 
                                                            WHERE id_solicitacao = %s
                                                        """, (n_qtd, n_just.strip(), id_sol))
                                                        conn_re.commit()
                                                st.success("Item devolvido para análise!")
                                                email_item_revisado_planejamento(id_sol, row['descricao'], f"{row['cd_origem']} -> {row['cd_destino']}", n_qtd, n_just.strip())
                                                st.rerun()
                                                
                                with col_btn_del:
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    if st.button("🗑️ Excluir Produto", key=f"del_prod_{id_sol}", type="primary", use_container_width=True):
                                        with get_conn(CRED_OP) as conn_del:
                                            with conn_del.cursor() as cur:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'Cancelado' WHERE id_solicitacao = %s", (id_sol,))
                                                conn_del.commit()
                                        st.toast(f"Produto #{id_sol} excluído da carga!")
                                        st.rerun()
            except Exception as e:
                st.error(f"Erro ao monitorar itens: {e}")

    # =========================================================================
    # MÓDULO DE PLANEJAMENTO
    # =========================================================================
    elif st.session_state.depto == "Planejamento":
        st.header("📊 Módulo de Planejamento - Avaliação de Demandas")
        tab_aprov, tab_agend = st.tabs(["📋 Aprovar Linhas de Solicitação (Lote)", "📅 Agendar Janelas de Doca (Consolidado)"])
        
        with tab_aprov:
            try:
                with get_conn(CRED_OP) as conn_op:
                    df_sol = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status_atual = 'Pendente Aprovação' ORDER BY id_solicitacao ASC", conn_op)
                
                if df_sol.empty:
                    st.info("Nenhum item pendente de aprovação.")
                else:
                    st.subheader("Avaliação Individual de Itens via Checkbox")
                    st.markdown("Marque **Aprovar** ou **Reprovar** para cada linha comercial e submeta o lote unificado ao final.")
                    
                    with st.form("form_planejamento_lote_coletivo"):
                        lista_respostas_planejamento = []
                        
                        for idx, r in df_sol.iterrows():
                            id_sol = r['id_solicitacao']
                            
                            with st.container(border=True):
                                st.markdown(f"**Item #{id_sol}** — {r['cod_produto']} - {r['descricao']}")
                                st.write(f"**Rota:** {r['cd_origem']} ➔ {r['cd_destino']} | **Qtd Solicitada:** {r['volume_solicitado']} {r['unidade_medida']} | **Solicitante:** {r['criado_por']}")
                                if r['justificativa_compras']:
                                    st.warning(f"⚠️ **Observação de Compras:** {r['justificativa_compras']}")
                                
                                col_aprov, col_reprov, col_motivo = st.columns([1.5, 1.5, 5])
                                
                                chk_aprovado = col_aprov.checkbox("🟢 Aprovar", key=f"chk_ap_{id_sol}")
                                chk_reprovado = col_reprov.checkbox("🔴 Reprovar", key=f"chk_rp_{id_sol}")
                                input_motivo = col_motivo.text_input("Se reprovar, informe o motivo", value="", key=f"txt_mot_{id_sol}")
                                
                                lista_respostas_planejamento.append({
                                    "id_sol": id_sol, "aprovado": chk_aprovado, "reprovado": chk_reprovado, "motivo": input_motivo, "row": r
                                })
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_submeter_tudo = st.form_submit_button("💾 Finalizar e Submeter Decisões do Lote", type="primary", use_container_width=True)
                        
                        if btn_submeter_tudo:
                            erros_validacao = False
                            lote_update_aprovados = []
                            lote_update_recusados = []
                            
                            for item in lista_respostas_planejamento:
                                if item['aprovado'] and item['reprovado']:
                                    st.error(f"Erro no Item #{item['id_sol']}: Não selecione 'Aprovar' e 'Reprovar' ao mesmo tempo.")
                                    erros_validacao = True
                                if item['reprovado'] and item['motivo'].strip() == "":
                                    st.error(f"Erro no Item #{item['id_sol']}: Se marcar como reprovado, o preenchimento do motivo é obrigatório.")
                                    erros_validacao = True
                                    
                                if not erros_validacao:
                                    if item['aprovado']:
                                        lote_update_aprovados.append(item)
                                    elif item['reprovado']:
                                        lote_update_recusados.append(item)
                                        
                            if not erros_validacao:
                                total_processados = len(lote_update_aprovados) + len(lote_update_recusados)
                                
                                if total_processados == 0:
                                    st.error("Nenhuma decisão de aprovação ou reprovação foi selecionada no lote.")
                                else:
                                    with get_conn(CRED_OP) as conn_processa:
                                        with conn_processa.cursor() as cur:
                                            for item in lote_update_aprovados:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'Aprovado', data_ultima_atualizacao = NOW() WHERE id_solicitacao = %s", (item['id_sol'],))
                                            for item in lote_update_recusados:
                                                cur.execute("UPDATE solicitacoes_transferencia SET status_atual = 'Recusado', justificativa_recusa = %s, data_ultima_atualizacao = NOW() WHERE id_solicitacao = %s", (item['motivo'].strip(), item['id_sol']))
                                        conn_processa.commit()
                                    
                                    # CORREÇÃO INTEGRADA AQUI:
                                    if lote_update_aprovados:
                                        html_ap = "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'><tr style='background-color:#e8f5e9;'><th>ID</th><th>Produto</th><th>Rota</th><th>Quantidade</th></tr>"
                                        emails_cds_envolvidos = []
                                        
                                        for item in lote_update_aprovados:
                                            r = item['row']
                                            html_ap += f"<tr><td>#{item['id_sol']}</td><td>{r['cod_produto']} - {r['descricao']}</td><td>{r['cd_origem']} ➔ {r['cd_destino']}</td><td>{r['volume_solicitado']} {r['unidade_medida']}</td></tr>"
                                            
                                            # Busca e-mails do CD de Origem para que eles recebam o e-mail de separação
                                            emails_orig = obter_emails_destinatarios(r['cd_origem'])
                                            if isinstance(emails_orig, list):
                                                emails_cds_envolvidos.extend(emails_orig)
                                            else:
                                                emails_cds_envolvidos.append(emails_orig)

                                        html_ap += "</table>"
                                        emails_cds_envolvidos = list(set(emails_cds_envolvidos))
                                        
                                        # Dispara e-mail para Planejamento + Responsáveis dos CDs de Origem
                                        email_lote_aprovados_planejamento(html_ap, len(lote_update_aprovados), emails_cds_envolvidos)
                                        
                                    if lote_update_recusados:
                                        html_rp = "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'><tr style='background-color:#ffebee;'><th>ID</th><th>Produto</th><th>Rota</th><th>Quantidade</th><th>Motivo da Recusa</th></tr>"
                                        for item in lote_update_recusados:
                                            r = item['row']
                                            html_rp += f"<tr><td>#{item['id_sol']}</td><td>{r['cod_produto']} - {r['descricao']}</td><td>{r['cd_origem']} ➔ {r['cd_destino']}</td><td>{r['volume_solicitado']} {r['unidade_medida']}</td><td style='color:#d32f2f;'><b>{item['motivo']}</b></td></tr>"
                                        html_rp += "</table>"
                                        email_lote_recusados_planejamento(html_rp, len(lote_update_recusados))
                                        
                                    st.success(f"Lote processado com sucesso! {len(lote_update_aprovados)} itens aprovados e {len(lote_update_recusados)} itens recusados.")
                                    st.rerun()
            except Exception as e:
                st.error(f"Erro no fluxo de aprovação do planejamento: {e}")

        with tab_agend:
            try:
                with get_conn(CRED_OP) as conn_op:
                    df_ag = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status_atual = 'Em Trânsito'", conn_op)
                
                if df_ag.empty:
                    st.info("Nenhuma carga aguardando agendamento logístico de doca.")
                else:
                    st.subheader("Controle de Janelas por Lote Consolidado")
                    df_ag['data_formatada'] = pd.to_datetime(df_ag['data_criacao']).dt.date
                    df_ag['chave_agrupamento'] = df_ag['cd_origem'] + " ➔ " + df_ag['cd_destino'] + " (" + df_ag['data_formatada'].astype(str) + ")"
                    
                    grupos_agendamento = df_ag['chave_agrupamento'].unique()
                    
                    for idx_g, nome_grupo in enumerate(grupos_agendamento):
                        df_sub_ag = df_ag[df_ag['chave_agrupamento'] == nome_grupo]
                        
                        transportadora_vinculada = df_sub_ag['transportadora'].iloc[0]
                        data_prevista_vinculada = pd.to_datetime(df_sub_ag['data_prevista_entrega'].iloc[0]).strftime('%d/%m/%Y')
                        cd_destino_carga = df_sub_ag['cd_destino'].iloc[0]
                        
                        total_volumes = int(df_sub_ag['qtd_volumes_separado'].sum())
                        total_peso = float(df_sub_ag['peso_total_bruto_kg'].sum())
                        total_cubagem = float(df_sub_ag['tamanho_cubico_m3'].sum())
                        lista_ids_grupo = df_sub_ag['id_solicitacao'].tolist()
                        
                        with st.container(border=True):
                            st.markdown(f"### 📅 Agendamento de Doca: {nome_grupo}")
                            st.markdown(f"**Transportadora:** {transportadora_vinculada} | **Previsão:** {data_prevista_vinculada}")
                            
                            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                            col_m1.metric("Total Volumes", f"{total_volumes} cx")
                            col_m2.metric("Peso Bruto", f"{total_peso:,.1f} KG")
                            col_m3.metric("Cubagem", f"{total_cubagem:.3f} m³")
                            col_m4.metric("Itens no Lote", f"{len(df_sub_ag)} prod.")
                            
                            with st.form(f"form_agenda_grupo_{idx_g}"):
                                col_d, col_h = st.columns(2)
                                dt_ag = col_d.date_input("Data para Descarregamento", key=f"dag_g_{idx_g}")
                                hr_ag = col_h.text_input("Horário da Janela (Ex: 08:30)", key=f"hag_g_{idx_g}")
                                
                                if st.form_submit_button("🔒 Confirmar Janela de Entrega para o Lote", use_container_width=True):
                                    if hr_ag.strip() == "":
                                        st.error("Informe a hora exata da janela de doca.")
                                    else:
                                        with get_conn(CRED_OP) as conn_up:
                                            with conn_up.cursor() as cur:
                                                cur.execute("""
                                                    UPDATE solicitacoes_transferencia 
                                                    SET data_agendada_final = %s, hora_agendada_final = %s, status_atual = 'Agendado', data_ultima_atualizacao = NOW()
                                                    WHERE id_solicitacao = ANY(%s)
                                                """, (dt_ag, hr_ag.strip(), lista_ids_grupo))
                                            conn_up.commit()
                                                
                                        st.success(f"Janela de doca salva para o lote.")
                                        email_modulo_5_resumido(nome_grupo, cd_destino_carga, dt_ag, hr_ag.strip(), len(lista_ids_grupo))
                                        st.rerun()
            except Exception as e:
                st.error(f"Erro no agendamento: {e}")

    # =========================================================================
    # MÓDULO DE TRANSPORTES
    # =========================================================================
    elif st.session_state.depto == "Transportes":
        st.header("🚛 Módulo de Carga e Contratação de Fretes")
        try:
            with get_conn(CRED_OP) as conn_op:
                df_tr = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status_atual = 'Pronto para Transporte'", conn_op)
            
            if df_tr.empty:
                st.info("Sem cargas liberadas para transporte no momento.")
            else:
                st.subheader("Fila de Expedição Consolidada")
                df_tr['data_formatada'] = pd.to_datetime(df_tr['data_criacao']).dt.date
                df_tr['chave_agrupamento'] = df_tr['cd_origem'] + " ➔ " + df_tr['cd_destino'] + " (" + df_tr['data_formatada'].astype(str) + ")"
                
                grupos_carga = df_tr['chave_agrupamento'].unique()
                
                for idx_g, nome_grupo in enumerate(grupos_carga):
                    df_sub_grupo = df_tr[df_tr['chave_agrupamento'] == nome_grupo]
                    
                    total_volumes = int(df_sub_grupo['qtd_volumes_separado'].sum())
                    total_peso_bruto = float(df_sub_grupo['peso_total_bruto_kg'].sum())
                    total_peso_liquido = float(df_sub_grupo['peso_total_liquido_kg'].sum())
                    total_cubagem = float(df_sub_grupo['tamanho_cubico_m3'].sum())
                    total_palets = int(df_sub_grupo['qtd_unidades_por_palet'].sum())
                    lista_ids_grupo = df_sub_grupo['id_solicitacao'].tolist()
                    
                    with st.container(border=True):
                        st.markdown(f"### 📦 Solicitação de Carga: {nome_grupo}")
                        
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("Soma Volumes Real", f"{total_volumes} cx")
                        c2.metric("Soma Peso Bruto", f"{total_peso_bruto:,.1f} KG")
                        c3.metric("Soma Peso Líquido", f"{total_peso_liquido:,.1f} KG")
                        c4.metric("Cubagem Total", f"{total_cubagem:.3f} m³")
                        c5.metric("Total Palets", f"{total_palets} PLT")
                        
                        with st.form(f"form_despacho_grupo_{idx_g}"):
                            col_t, col_d = st.columns(2)
                            transp = col_t.text_input("Nome da Transportadora / Motorista", key=f"tname_g_{idx_g}")
                            dt_p = col_d.date_input("Previsão de Chegada no Destino", key=f"dtp_g_{idx_g}")
                            
                            if st.form_submit_button("🚀 Despachar Carga Consolidada (Lote)", type="primary", use_container_width=True):
                                if transp.strip() == "":
                                    st.error("Por favor, preencha o nome da transportadora.")
                                else:
                                    with get_conn(CRED_OP) as conn_up:
                                        with conn_up.cursor() as cur:
                                            cur.execute("""
                                                UPDATE solicitacoes_transferencia 
                                                SET data_prevista_entrega = %s, transportadora = %s, status_atual = 'Em Trânsito', data_ultima_atualizacao = NOW()
                                                WHERE id_solicitacao = ANY(%s)
                                            """, (dt_p, transp.strip(), lista_ids_grupo))
                                            conn_up.commit()
                                    
                                    st.success(f"Carga despachada.")
                                    email_modulo_4_resumido(nome_grupo, transp.strip(), dt_p, len(lista_ids_grupo))
                                    st.rerun()
        except Exception as e:
            st.error(f"Erro no módulo de transportes resumido: {e}")

    # =========================================================================
    # GESTÃO DE CD (ORIGEM EM LOTE + DESTINO CONSOLIDADO COM CONFERÊNCIA)
    # =========================================================================
    elif st.session_state.depto == "CD":
        cd_logado = st.session_state.cd_user
        st.header(f"🏢 Painel Operacional de Movimentação - CD {cd_logado}")
        tab_origem, tab_destino = st.tabs(["📤 Cargas Saindo (Origem)", "📥 Cargas Chegando (Destino Consolidado)"])
        
        with tab_origem:
            try:
                with get_conn(CRED_OP) as conn_op:
                    query = """
                        SELECT id_solicitacao, cod_produto, descricao, volume_solicitado, unidade_medida, cd_origem, cd_destino, data_criacao
                        FROM solicitacoes_transferencia 
                        WHERE status_atual = 'Aprovado' AND separado = FALSE AND cd_origem = %s
                        ORDER BY data_criacao ASC, id_solicitacao ASC
                    """
                    df_ori = pd.read_sql(query, conn_op, params=(cd_logado,))
                
                if df_ori.empty:
                    st.info(f"Nenhuma separação pendente para a unidade {cd_logado}.")
                else:
                    df_ori['data_formatada'] = pd.to_datetime(df_ori['data_criacao']).dt.date
                    df_ori['chave_agrupamento'] = df_ori['cd_origem'] + " ➔ " + df_ori['cd_destino'] + " (" + df_ori['data_formatada'].astype(str) + ")"
                    
                    grupos = df_ori['chave_agrupamento'].unique()
                    
                    for g_idx, grupo_nome in enumerate(grupos):
                        df_grupo = df_ori[df_ori['chave_agrupamento'] == grupo_nome]
                        
                        with st.container(border=True):
                            st.subheader(f"📦 Solicitação de Transferência: {grupo_nome}")
                            
                            with st.form(f"form_grupo_separa_{g_idx}"):
                                lista_coleta_inputs = []
                                
                                for _, row in df_grupo.iterrows():
                                    id_sol = row['id_solicitacao']
                                    st.markdown(f"**Item #{id_sol}** — {row['cod_produto']} - {row['descricao']}")
                                    col_chk, col_sep = st.columns([1.2, 8.8])
                                    
                                    marcado = col_chk.checkbox("Separado?", key=f"chk_sep_{id_sol}")
                                    v_sep = col_sep.number_input("Qtd. Real", min_value=1, value=int(row['volume_solicitado']), key=f"vsep_{id_sol}")
                                    
                                    lista_coleta_inputs.append({
                                        "id_sol": id_sol, "marcado": marcado, "v_sep": v_sep, "desc": row['descricao']
                                    })
                                    st.markdown("<hr style='margin:10px 0; border:0.5px dashed #ccc;'>", unsafe_allow_html=True)
                                
                                st.markdown("### 📊 Dados Totais da Carga (Consolidado)")
                                col_tot_plt, col_tot_pb, col_tot_pl = st.columns(3)
                                total_palets_lote = col_tot_plt.number_input("Quantidade de Palets", min_value=1, value=1, key=f"tot_plt_{g_idx}")
                                total_pb_lote = col_tot_pb.number_input("P. Bruto (KG)", min_value=0.0, step=0.5, key=f"tot_pb_{g_idx}")
                                total_pl_lote = col_tot_pl.number_input("P.Liq. (KG)", min_value=0.0, step=0.5, key=f"tot_pl_{g_idx}")
                                
                                if st.form_submit_button("💾 Salvar Itens Selecionados do Lote", type="primary", use_container_width=True):
                                    itens_marcados = [item for item in lista_coleta_inputs if item['marcado']]
                                    itens_processados_cont = len(itens_marcados)
                                    
                                    if itens_processados_cont == 0:
                                        st.error("Nenum item foi marcado como separado.")
                                    else:
                                        sum_vol = sum(item['v_sep'] for item in itens_marcados)
                                        pb_por_item = round(total_pb_lote / itens_processados_cont, 2)
                                        pl_por_item = round(total_pl_lote / itens_processados_cont, 2)
                                        plt_por_item = int(max(1, total_palets_lote // itens_processados_cont))
                                        
                                        with get_conn(CRED_OP) as conn_up:
                                            with conn_up.cursor() as cur:
                                                for item in itens_marcados:
                                                    cur.execute("""
                                                        UPDATE solicitacoes_transferencia 
                                                        SET separado = TRUE, 
                                                            qtd_volumes_separado = %s, 
                                                            peso_total_bruto_kg = %s, 
                                                            peso_total_liquido_kg = %s, 
                                                            tamanho_cubico_m3 = 0.0, 
                                                            qtd_unidades_por_palet = %s, 
                                                            status_atual = 'Pronto para Transporte', 
                                                            data_ultima_atualizacao = NOW()
                                                        WHERE id_solicitacao = %s
                                                    """, (item['v_sep'], pb_por_item, pl_por_item, plt_por_item, item['id_sol']))
                                            conn_up.commit()
                                        
                                        st.success("Itens processados e despachados para a fila de frete!")
                                        dados_macros = {'qtd_vol': sum_vol, 'peso_bruto': total_pb_lote, 'cubagem': 0.0}
                                        email_modulo_3_resumido(grupo_nome, dados_macros, itens_processados_cont)
                                        st.rerun()
            except Exception as e:
                st.error(f"Erro na origem do CD: {e}")

        with tab_destino:
            try:
                with get_conn(CRED_OP) as conn_op:
                    df_dest = pd.read_sql("SELECT * FROM solicitacoes_transferencia WHERE status_atual = 'Agendado' AND cd_destino = %s", conn_op, params=(cd_logado,))
                
                if df_dest.empty:
                    st.info("Nenhuma carga agendada para recebimento nesta filial.")
                else:
                    st.subheader("Recebimento e Conferência Física de Cargas")
                    st.markdown("Marque o checkbox de conferência e valide os volumes físicos recebidos por produto do lote.")

                    df_dest['data_formatada'] = pd.to_datetime(df_dest['data_criacao']).dt.date
                    df_dest['chave_agrupamento'] = df_dest['cd_origem'] + " ➔ " + df_dest['cd_destino'] + " (" + df_dest['data_formatada'].astype(str) + ")"
                    
                    grupos_destino = df_dest['chave_agrupamento'].unique()
                    
                    for idx_d, nome_grupo in enumerate(grupos_destino):
                        df_sub_dest = df_dest[df_dest['chave_agrupamento'] == nome_grupo]
                        
                        data_agenda_doca = pd.to_datetime(df_sub_dest['data_agendada_final'].iloc[0]).strftime('%d/%m/%Y')
                        hora_agenda_doca = df_sub_dest['hora_agendada_final'].iloc[0]
                        transp_responsavel = df_sub_dest['transportadora'].iloc[0]
                        
                        with st.container(border=True):
                            st.markdown(f"### 📥 Recebimento de Carga: {nome_grupo}")
                            st.caption(f"📅 **Janela de Doca:** {data_agenda_doca} às {hora_agenda_doca} | 🚛 **Transporte:** {transp_responsavel}")
                            
                            with st.form(f"form_recebimento_lote_{idx_d}"):
                                lista_conferência_produtos = []
                                
                                for inner_idx, r in df_sub_dest.iterrows():
                                    id_solic = r['id_solicitacao']
                                    qtd_esperada = int(r['qtd_volumes_separado'] if r['qtd_volumes_separado'] is not None else r['volume_solicitado'])
                                    
                                    col_p_info, col_p_chk, col_p_qtd = st.columns([5, 1.5, 2])
                                    
                                    col_p_info.markdown(f"**Item #{id_solic}** — {r['cod_produto']} - {r['descricao']}  \n*Unidade Medida:* {r['unidade_medida']} | *Qtd Despachada CD Origem:* **{qtd_esperada}**")
                                    
                                    marcado_conf = col_p_chk.checkbox("Conferido", key=f"chk_conf_{id_solic}")
                                    qtd_recebida_fisica = col_p_qtd.number_input("Qtd Recebida", min_value=0, value=qtd_esperada, key=f"val_conf_{id_solic}")
                                    
                                    lista_conferência_produtos.append({
                                        "id_sol": id_solic, "conferido": marcado_conf, "qtd_física": qtd_recebida_fisica, "row": r
                                    })
                                    st.markdown("<hr style='margin:8px 0; border:0.5px dotted #eee;'>", unsafe_allow_html=True)
                                
                                chk_termo = st.checkbox("Confirmo a conferência física e o encerramento das paletas acima descritas", key=f"chk_termo_{idx_d}")
                                
                                if st.form_submit_button("🏁 Finalizar Recebimento e Atualizar Estoque (Lote)", use_container_width=True):
                                    if not chk_termo:
                                        st.error("É obrigatório marcar o termo de validação física para encerrar o lote.")
                                    else:
                                        validacao_itens_ok = True
                                        for item in lista_conferência_produtos:
                                            if not item['conferido']:
                                                st.error(f"Por favor, confirme a verificação do Item #{item['id_sol']} marcando a caixa 'Conferido'.")
                                                validacao_itens_ok = False
                                        
                                        if validacao_itens_ok:
                                            with get_conn(CRED_OP) as conn_final:
                                                with conn_final.cursor() as cur:
                                                    html_tabela_email = "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'><tr style='background-color:#e1f5fe;'><th>ID Item</th><th>Produto</th><th>Qtd Despachada</th><th>Qtd Recebida</th></tr>"
                                                    
                                                    for item in lista_conferência_produtos:
                                                        r_dados = item['row']
                                                        qtd_desp = int(r_dados['qtd_volumes_separado'] if r_dados['qtd_volumes_separado'] is not None else r_dados['volume_solicitado'])
                                                        
                                                        cur.execute("""
                                                            UPDATE solicitacoes_transferencia 
                                                            SET status_atual = 'Concluído', 
                                                                volume_recebido = %s, 
                                                                data_ultima_atualizacao = NOW()
                                                            WHERE id_solicitacao = %s
                                                        """, (item['qtd_física'], item['id_sol']))
                                                        
                                                        estilo_aviso = "style='color:#d32f2f; font-weight:bold;'" if item['qtd_física'] != qtd_desp else ""
                                                        html_tabela_email += f"<tr><td>#{item['id_sol']}</td><td>{r_dados['cod_produto']} - {r_dados['descricao']}</td><td>{qtd_desp}</td><td {estilo_aviso}>{item['qtd_física']}</td></tr>"
                                                    
                                                    html_tabela_email += "</table>"
                                                    conn_final.commit()
                                            
                                            st.success(f"Excelente! Recebimento do lote finalizado com sucesso.")
                                            email_lote_concluido(nome_grupo, len(lista_conferência_produtos), html_tabela_email)
                                            st.rerun()
            except Exception as e:
                st.error(f"Erro no fechamento do CD destino: {e}")
