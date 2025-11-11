import requests
import json
import csv

ODOO_URL = "https://erp.cloudgenia.app"
DB_NAME = input("Ingrese el nombre de la base de datos: ").strip()
USERNAME = input("Ingrese el nombre de usuario: ").strip()
PASSWORD = input("Ingrese la contraseña: ").strip()


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
        print("Error de autenticación. Revisa usuario, base o contraseña.")
        print("Respuesta:", data)
        return None

    print(f"Autenticado correctamente. UID = {uid}")
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
        print("Error al obtener proyectos:")
        print(json.dumps(data, indent=4))
        return []

    projects = data["result"]
    print(f"Total de proyectos encontrados: {len(projects)}")
    return projects


def get_tasks_by_project(url: str, db: str, uid: int, password: str, project_id: int):
    """Obtiene todas las tareas de un proyecto con eliminación dinámica de campos inválidos."""
    fields = ["id", "name", "stage_id", "user_ids", "date_deadline", "create_date", "kanban_state", "assigned_user_id"]

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
            tasks = data["result"]
            print(f"Total de tareas encontradas para el proyecto {project_id}: {len(tasks)}")
            return tasks

        # Manejar errores de campos inválidos
        if "error" in data and "Invalid field" in str(data["error"]):
            invalid_field = str(data["error"]["data"]["message"]).split("'")[1]
            print(f"Campo inválido detectado: {invalid_field}. Reintentando sin ese campo...")
            if invalid_field in fields:
                fields.remove(invalid_field)
            continue

        print("Error al obtener tareas:")
        print(json.dumps(data, indent=4))
        return []

    print("No fue posible obtener tareas: todos los campos fallaron.")
    return []


def export_to_csv(data, filename="datos_odoo.csv"):
    """Guarda los datos en un archivo CSV."""
    if not data:
        print("No hay datos para exportar.")
        return

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    print(f"Datos exportados correctamente a {filename}")


if __name__ == "__main__":
    print("Conectando con Odoo...\n")

    uid = authenticate(ODOO_URL, DB_NAME, USERNAME, PASSWORD)
    if not uid:
        exit()

    projects = get_projects(ODOO_URL, DB_NAME, uid, PASSWORD)

    print("\nLista de proyectos disponibles:")
    for p in projects:
        print(f"   {p['id']}: {p['name']} (Activo: {p['active']})")

    choice = input("\n¿Deseas extraer las tareas de un proyecto? (s/n): ").strip().lower()

    if choice == "s":
        try:
            project_id = int(input("Ingrese el ID del proyecto: ").strip())
        except ValueError:
            print("ID inválido. Debe ser un número entero.")
            exit()

        tasks = get_tasks_by_project(ODOO_URL, DB_NAME, uid, PASSWORD, project_id)

        print("\nPrimeras tareas encontradas:")
        for t in tasks[:10]:
            stage_name = t["stage_id"][1] if t.get("stage_id") else "Sin etapa"
            print(f"   {t['id']}: {t['name']} ({stage_name})")

        export_choice = input("\n¿Deseas exportar las tareas a CSV? (s/n): ").strip().lower()
        if export_choice == "s":
            export_to_csv(tasks, f"tareas_proyecto_{project_id}.csv")
    else:
        print("\nOperación finalizada.")
