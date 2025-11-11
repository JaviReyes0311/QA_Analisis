import streamlit as st
import pandas as pd
import requests
import json

# =====================================================
#  FUNCIONES PARA CONECTAR CON ODOO
# =====================================================

def authenticate(url: str, db: str, username: str, password: str) -> int:
    """Autentica un usuario en Odoo y devuelve el UID."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "common",
            "method": "authenticate",
            "args": [db, username, password, {}]
        },
        "id": 1
    }

    res = requests.post(f"{url}/jsonrpc", json=payload)
    data = res.json()
    uid = data.get("result")

    if not uid:
        st.error("Error de autenticación. Revisa usuario, base o contraseña.")
        st.json(data)
        return None

    st.success(f"Autenticado correctamente. UID = {uid}")
    return uid


def get_projects(url: str, db: str, uid: int, password: str):
    """Obtiene todos los proyectos desde Odoo."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [
                db,
                uid,
                password,
                "project.project",
                "search_read",
                [
                    [],
                    ["id", "name", "user_id", "company_id", "create_date", "active"]
                ]
            ]
        },
        "id": 2
    }

    res = requests.post(f"{url}/jsonrpc", json=payload)
    data = res.json()

    if "result" not in data:
        st.error("Error al obtener proyectos.")
        st.json(data)
        return []

    return data["result"]


def get_tasks_by_project(url: str, db: str, uid: int, password: str, project_id: int):
    """Obtiene todas las tareas de un proyecto incluyendo child_ids y campos clave."""
    fields = [
        "id", "name", "stage_id", "priority", "tag_ids",
        "create_uid", "child_ids", "project_id", "user_ids",
        "date_deadline", "create_date"
    ]

    while fields:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    db,
                    uid,
                    password,
                    "project.task",
                    "search_read",
                    [[["project_id", "=", project_id]], fields]
                ]
            },
            "id": 3
        }

        res = requests.post(f"{url}/jsonrpc", json=payload)
        data = res.json()

        if "result" in data:
            return data["result"]

        if "error" in data and "Invalid field" in str(data["error"]):
            invalid_field = str(data["error"]["data"]["message"]).split("'")[1]
            st.warning(f"Campo inválido detectado: {invalid_field}. Reintentando sin ese campo...")
            if invalid_field in fields:
                fields.remove(invalid_field)
            continue

        st.error("Error al obtener tareas.")
        st.json(data)
        return []

    st.error("No fue posible obtener tareas: todos los campos fallaron.")
    return []


# =====================================================
#  INTERFAZ STREAMLIT
# =====================================================

ODOO_URL = "https://erp.cloudgenia.app"

st.set_page_config(page_title="Explorador Odoo", layout="wide")

st.title("Explorador de tareas Odoo - Cloudgenia")

with st.sidebar:
    st.header("Conexión a Odoo")
    db = st.text_input("Base de datos")
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Conectar"):
        uid = authenticate(ODOO_URL, db, username, password)
        if uid:
            st.session_state["uid"] = uid
            st.session_state["db"] = db
            st.session_state["username"] = username
            st.session_state["password"] = password

# =====================================================
#  SECCIÓN DE PROYECTOS Y TAREAS
# =====================================================

if "uid" in st.session_state:
    projects = get_projects(ODOO_URL, st.session_state["db"], st.session_state["uid"], st.session_state["password"])
    if not projects:
        st.warning("No se encontraron proyectos.")
        st.stop()

    project_options = {p["name"]: p["id"] for p in projects}
    selected_project = st.selectbox("Selecciona un proyecto", list(project_options.keys()))

    if selected_project:
        project_id = project_options[selected_project]
        tasks = get_tasks_by_project(
            ODOO_URL,
            st.session_state["db"],
            st.session_state["uid"],
            st.session_state["password"],
            project_id
        )

        if not tasks:
            st.warning("No se encontraron tareas para este proyecto.")
            st.stop()

        # Convertir a DataFrame
        df = pd.DataFrame(tasks)

        # =====================================================
        #  FILTROS
        # =====================================================
        st.sidebar.subheader("Filtros")

        stage_options = sorted({t["stage_id"][1] for t in tasks if t.get("stage_id")})
        selected_stage = st.sidebar.selectbox("Etapa", ["Todos"] + stage_options)

        priorities = sorted({t["priority"] for t in tasks if t.get("priority")})
        selected_priority = st.sidebar.selectbox("Prioridad", ["Todas"] + priorities)

        creators = sorted({t["create_uid"][1] for t in tasks if t.get("create_uid")})
        selected_creator = st.sidebar.selectbox("Creado por", ["Todos"] + creators)

        # Aplicar filtros
        filtered = []
        for t in tasks:
            if selected_stage != "Todos" and (not t.get("stage_id") or t["stage_id"][1] != selected_stage):
                continue
            if selected_priority != "Todas" and t.get("priority") != selected_priority:
                continue
            if selected_creator != "Todos" and (not t.get("create_uid") or t["create_uid"][1] != selected_creator):
                continue
            filtered.append(t)

        st.subheader(f"Tareas encontradas: {len(filtered)}")
        df_filtered = pd.DataFrame(filtered)

        if not df_filtered.empty:
            # Mostrar tabla resumida
            cols = ["id", "name", "stage_id", "priority", "create_uid", "child_ids"]
            display_cols = [c for c in cols if c in df_filtered.columns]
            st.dataframe(df_filtered[display_cols])

            # =====================================================
            #  DETALLE DE TAREA
            # =====================================================
            st.subheader("Detalle de tarea")

            selected_task_name = st.selectbox(
                "Selecciona una tarea para ver su detalle",
                df_filtered["name"].tolist()
            )

            if selected_task_name:
                task_data = df_filtered[df_filtered["name"] == selected_task_name].iloc[0].to_dict()
                st.json(task_data)

                # Mostrar subtareas si existen
                if task_data.get("child_ids"):
                    st.markdown("**Subtareas (child_ids):**")
                    st.write(task_data["child_ids"])
                else:
                    st.info("Esta tarea no tiene subtareas asociadas.")
        else:
            st.warning("No hay tareas que coincidan con los filtros.")
else:
    st.info("Introduce tus credenciales en el panel lateral para comenzar.")
