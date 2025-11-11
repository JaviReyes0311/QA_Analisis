import requests
import json
import csv

# =======================
# CONFIGURACIÓN GLOBAL
# =======================
ODOO_URL = "https://erp.cloudgenia.app"
DB_NAME = "cloudgenia"                     # ✅ nombre real de la base
USERNAME = "admin@cloudgenia.com"          # tu usuario real
PASSWORD = "TU_CONTRASEÑA_LOCAL"           # tu contraseña de Odoo


# =======================
# FUNCIONES AUXILIARES
# =======================

def authenticate(url, db, username, password):
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
    res = requests.post(f"{url}/jsonrpc", json=payload).json()
    uid = res.get("result")
    if not uid:
        print("❌ Error de autenticación. Revisa usuario, base o contraseña.")
        return None
    print(f"✅ Autenticado correctamente. UID = {uid}")
    return uid


def odoo_call(url, db, uid, password, model, method, args, kwargs=None):
    """Ejecuta una llamada genérica a un modelo de Odoo."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [db, uid, password, model, method, args],
        },
        "id": 2
    }
    if kwargs:
        payload["params"]["kwargs"] = kwargs
    res = requests.post(f"{url}/jsonrpc", json=payload).json()
    return res.get("result", [])


def get_projects(url, db, uid, password):
    """Obtiene todos los proyectos."""
    return odoo_call(
        url, db, uid, password,
        "project.project", "search_read",
        [[], ["id", "name", "user_id", "company_id", "active"]],
    )


def get_tasks_by_project(url, db, uid, password, project_id):
    """Obtiene todas las tareas de un proyecto específico."""
    domain = [[["project_id", "=", project_id]]]
    fields = ["id", "name", "user_id", "stage_id", "date_deadline", "create_date", "kanban_state"]
    return odoo_call(url, db, uid, password, "project.task", "search_read", domain + [fields])


def export_to_csv(data, filename):
    """Guarda los resultados en CSV."""
    if not data:
        print("⚠️ No hay datos para exportar.")
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ Datos exportados correctamente a {filename}")


# =======================
# SCRIPT PRINCIPAL
# =======================
if __name__ == "__main__":
    print("🚀 Conectando con Odoo...\n")

    uid = authenticate(ODOO_URL, DB_NAME, USERNAME, PASSWORD)
    if not uid:
        exit()

    # === Obtener proyectos ===
    projects = get_projects(ODOO_URL, DB_NAME, uid, PASSWORD)
    print(f"\n📦 Proyectos encontrados: {len(projects)}")
    for p in projects:
        print(f"  🔹 {p['id']}: {p['name']}")

    # === Preguntar si desea ver tareas ===
    choice = input("\n¿Deseas extraer las tareas de un proyecto? (s/n): ").strip().lower()

    if choice == "s":
        project_id = input("👉 Ingresa el ID del proyecto: ").strip()
        if not project_id.isdigit():
            print("⚠️ ID inválido. Debe ser numérico.")
        else:
            project_id = int(project_id)
            tasks = get_tasks_by_project(ODOO_URL, DB_NAME, uid, PASSWORD, project_id)
            print(f"\n📋 Tareas del proyecto {project_id}: {len(tasks)} encontradas")
            for t in tasks[:10]:  # mostrar solo las primeras 10
                print(f"   🔸 {t['id']}: {t['name']} ({t.get('stage_id', [''])[1] if t.get('stage_id') else 'Sin etapa'})")

            # Exportar a CSV
            export_to_csv(tasks, f"tareas_proyecto_{project_id}.csv")
    else:
        print("👌 Operación finalizada.")
