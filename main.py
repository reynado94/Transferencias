import streamlit as st
import datetime
import sqlite3
from datetime import date

# Conexión a la base de datos (se creará si no existe)
conn = sqlite3.connect('transferencias.db')
cursor = conn.cursor()

# Crear tablas si no existen
def crear_tablas():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empleados (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL CHECK (rol IN ('administrador', 'registrador', 'confirmador')),
            porcentaje_ganancia REAL NOT NULL DEFAULT 0.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transferencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_solicitud TEXT NOT NULL,
            remitente_nombre TEXT NOT NULL,
            destinatario_nombre TEXT NOT NULL,
            destinatario_telefono TEXT NOT NULL,
            capital REAL NOT NULL,
            fecha_confirmacion TEXT,
            confirmador_id INTEGER,
            registrador_id INTEGER NOT NULL,
            estado TEXT NOT NULL CHECK (estado IN ('solicitada', 'confirmada', 'entregada')),
            FOREIGN KEY (registrador_id) REFERENCES empleados (id),
            FOREIGN KEY (confirmador_id) REFERENCES empleados (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial_ediciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transferencia_id INTEGER NOT NULL,
            fecha_edicion TEXT NOT NULL,
            empleado_editor_id INTEGER NOT NULL,
            campo_editado TEXT NOT NULL,
            valor_anterior TEXT,
            valor_nuevo TEXT,
            FOREIGN KEY (transferencia_id) REFERENCES transferencias (id),
            FOREIGN KEY (empleado_editor_id) REFERENCES empleados (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ganancias_globales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado_id INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            ganancia_general REAL NOT NULL,
            ganancia_personalizada REAL NOT NULL,
            total_ganancia REAL NOT NULL,
            FOREIGN KEY (empleado_id) REFERENCES empleados (id)
        )
    ''')
    conn.commit()

# Verificar si hay empleados registrados
def hay_empleados_registrados():
    cursor.execute('SELECT COUNT(*) FROM empleados')
    return cursor.fetchone()[0] > 0

# Registrar primer administrador
def registrar_primer_administrador():
    st.warning("No hay usuarios registrados. Por favor, registre el primer administrador.")
    with st.form("registro_admin"):
        id_admin = st.number_input("ID del administrador:", step=1, format="%d", min_value=1)
        nombre_admin = st.text_input("Nombre completo:")
        porcentaje_admin = st.number_input("Porcentaje de ganancia (%):", min_value=0.0, max_value=100.0, value=10.0, step=0.1)
        
        if st.form_submit_button("Registrar Administrador"):
            if not nombre_admin:
                st.error("El nombre es obligatorio")
            else:
                agregar_empleado(id_admin, nombre_admin, 'administrador', porcentaje_admin)
                st.success("Administrador registrado con éxito. Ahora puede iniciar sesión.")
                st.rerun()

# Funciones para la gestión de datos
def agregar_empleado(id_empleado, nombre, rol, porcentaje_ganancia=0.0):
    cursor.execute('INSERT INTO empleados (id, nombre, rol, porcentaje_ganancia) VALUES (?, ?, ?, ?)', 
                  (id_empleado, nombre, rol, porcentaje_ganancia))
    conn.commit()
    st.success(f"Empleado {nombre} ({rol}) agregado con ID {id_empleado} y porcentaje de ganancia {porcentaje_ganancia:.2f}%.")

def calcular_ganancia_general(capital):
    """Calcula el 10% del capital como ganancia general"""
    return capital * 0.10

def distribuir_ganancias(transferencia_id):
    """Distribuye las ganancias de una transferencia a los empleados involucrados"""
    # Obtener datos de la transferencia
    cursor.execute('''
        SELECT capital, registrador_id, confirmador_id 
        FROM transferencias 
        WHERE id = ? AND estado = 'entregada'
    ''', (transferencia_id,))
    transferencia = cursor.fetchone()
    
    if not transferencia:
        return
    
    capital, registrador_id, confirmador_id = transferencia
    ganancia_general = calcular_ganancia_general(capital)
    fecha_actual = datetime.datetime.now()
    mes = fecha_actual.month
    anio = fecha_actual.year
    
    # Obtener porcentajes de ganancia para cada rol
    cursor.execute('SELECT porcentaje_ganancia FROM empleados WHERE id = ?', (registrador_id,))
    porcentaje_registrador = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT porcentaje_ganancia FROM empleados WHERE id = ?', (confirmador_id,))
    porcentaje_confirmador = cursor.fetchone()[0] or 0
    
    # El administrador recibe el resto de la ganancia general
    cursor.execute('SELECT id, porcentaje_ganancia FROM empleados WHERE rol = "administrador"')
    admin_data = cursor.fetchone()
    if admin_data:
        admin_id, porcentaje_admin = admin_data
    else:
        admin_id, porcentaje_admin = None, 0
    
    # Calcular ganancias para cada empleado
    ganancia_registrador = ganancia_general * (porcentaje_registrador / 100)
    ganancia_confirmador = ganancia_general * (porcentaje_confirmador / 100)
    ganancia_admin = ganancia_general * (porcentaje_admin / 100)
    
    # Registrar ganancias en la tabla de ganancias globales
    empleados_ganancias = [
        (registrador_id, mes, anio, ganancia_general, ganancia_registrador, ganancia_registrador),
        (confirmador_id, mes, anio, ganancia_general, ganancia_confirmador, ganancia_confirmador)
    ]
    
    if admin_id:
        empleados_ganancias.append(
            (admin_id, mes, anio, ganancia_general, ganancia_admin, ganancia_admin)
        )
    
    for empleado_id, mes, anio, gg, gp, total in empleados_ganancias:
        # Verificar si ya existe un registro para este empleado en el mes/año
        cursor.execute('''
            SELECT id FROM ganancias_globales 
            WHERE empleado_id = ? AND mes = ? AND anio = ?
        ''', (empleado_id, mes, anio))
        
        if cursor.fetchone():
            # Actualizar registro existente
            cursor.execute('''
                UPDATE ganancias_globales
                SET ganancia_general = ganancia_general + ?,
                    ganancia_personalizada = ganancia_personalizada + ?,
                    total_ganancia = total_ganancia + ?
                WHERE empleado_id = ? AND mes = ? AND anio = ?
            ''', (gg, gp, total, empleado_id, mes, anio))
        else:
            # Insertar nuevo registro
            cursor.execute('''
                INSERT INTO ganancias_globales 
                (empleado_id, mes, anio, ganancia_general, ganancia_personalizada, total_ganancia)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (empleado_id, mes, anio, gg, gp, total))
    
    conn.commit()

def registrar_transferencia(registrador_id, remitente_nombre, destinatario_nombre, destinatario_telefono, capital):
    fecha_solicitud = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    estado = 'solicitada'
    cursor.execute('''
        INSERT INTO transferencias 
        (fecha_solicitud, remitente_nombre, destinatario_nombre, destinatario_telefono, capital, registrador_id, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha_solicitud, remitente_nombre, destinatario_nombre, destinatario_telefono, capital, registrador_id, estado))
    conn.commit()
    transferencia_id = cursor.lastrowid
    st.info(f"Transferencia registrada (solicitada) con ID: {transferencia_id}. Esperando confirmación del confirmador.")
    return transferencia_id

def confirmar_transferencia_entregada(transferencia_id, confirmador_id):
    fecha_confirmacion = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        UPDATE transferencias
        SET estado = 'entregada', fecha_confirmacion = ?, confirmador_id = ?
        WHERE id = ? AND estado = 'solicitada'
    ''', (fecha_confirmacion, confirmador_id, transferencia_id))
    
    if cursor.rowcount > 0:
        conn.commit()
        # Distribuir ganancias ahora que la transferencia está entregada
        distribuir_ganancias(transferencia_id)
        st.success("Transferencia marcada como entregada y ganancias distribuidas.")
    else:
        st.error("Error: La transferencia no se pudo confirmar.")

def editar_transferencia(transferencia_id, empleado_editor_id, campo, nuevo_valor):
    campos_editables = {
        'remitente_nombre': 'TEXT',
        'destinatario_nombre': 'TEXT',
        'destinatario_telefono': 'TEXT',
        'capital': 'REAL'
    }
    if campo not in campos_editables:
        st.error(f"El campo '{campo}' no es editable.")
        return False

    cursor.execute(f'SELECT {campo} FROM transferencias WHERE id = ?', (transferencia_id,))
    valor_anterior = cursor.fetchone()[0]

    cursor.execute(f'UPDATE transferencias SET {campo} = ? WHERE id = ?', (nuevo_valor, transferencia_id))
    conn.commit()

    if cursor.rowcount > 0:
        fecha_edicion = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO historial_ediciones (transferencia_id, fecha_edicion, empleado_editor_id, campo_editado, valor_anterior, valor_nuevo)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (transferencia_id, fecha_edicion, empleado_editor_id, campo, str(valor_anterior), str(nuevo_valor)))
        conn.commit()
        st.info(f"Transferencia ID {transferencia_id}: El campo '{campo}' ha sido editado de '{valor_anterior}' a '{nuevo_valor}'.")
        return True
    else:
        st.error(f"No se pudo editar la transferencia ID {transferencia_id}. Verifique el ID.")
        return False

def listar_transferencias(rol, empleado_id=None):
    """
    Lista las transferencias según el rol del usuario.

    Args:
        rol: El rol del usuario ('administrador', 'registrador', 'confirmador').
        empleado_id: El ID del empleado (opcional, para filtrar por registrador o confirmador).
    """
    if rol == 'administrador':
        cursor.execute('''
            SELECT t.id, t.fecha_solicitud, t.remitente_nombre, t.destinatario_nombre, t.destinatario_telefono,
                   t.capital, t.fecha_confirmacion, e_reg.nombre, e_conf.nombre, t.estado
            FROM transferencias t
            JOIN empleados e_reg ON t.registrador_id = e_reg.id
            LEFT JOIN empleados e_conf ON t.confirmador_id = e_conf.id
            ORDER BY t.fecha_solicitud DESC
        ''')
        transferencias = cursor.fetchall()
    elif rol == 'registrador' and empleado_id:
        cursor.execute('''
            SELECT t.id, t.fecha_solicitud, t.remitente_nombre, t.destinatario_nombre, t.destinatario_telefono,
                   t.capital, t.fecha_confirmacion, e_reg.nombre, e_conf.nombre, t.estado
            FROM transferencias t
            JOIN empleados e_reg ON t.registrador_id = e_reg.id
            LEFT JOIN empleados e_conf ON t.confirmador_id = e_conf.id
            WHERE t.registrador_id = ?
            ORDER BY t.fecha_solicitud DESC
        ''', (empleado_id,))
        transferencias = cursor.fetchall()
    elif rol == 'confirmador' and empleado_id:
        cursor.execute('''
            SELECT t.id, t.fecha_solicitud, t.remitente_nombre, t.destinatario_nombre, t.destinatario_telefono,
                   t.capital, t.fecha_confirmacion, e_reg.nombre, e_conf.nombre, t.estado
            FROM transferencias t
            JOIN empleados e_reg ON t.registrador_id = e_reg.id
            LEFT JOIN empleados e_conf ON t.confirmador_id = e_conf.id
            WHERE t.estado = 'solicitada'
            ORDER BY t.fecha_solicitud DESC
        ''')
        transferencias = cursor.fetchall()
    else:
        st.warning("No se pueden listar las transferencias para este rol.")
        return

    if not transferencias:
        st.info("No hay transferencias registradas.")
        return

    st.subheader("Listado de Transferencias:")
    for transferencia in transferencias:
        id_transaccion, fecha_solicitud, remitente_nombre, destinatario_nombre, destinatario_telefono, capital, fecha_confirmacion, registrador_nombre, confirmador_nombre, estado = transferencia
        st.write(f"**ID:** {id_transaccion}, **Fecha Solicitud:** {fecha_solicitud}, **Remitente:** {remitente_nombre}, **Destinatario:** {destinatario_nombre} ({destinatario_telefono}), **Capital:** {capital}, **Fecha Confirmación:** {fecha_confirmacion if fecha_confirmacion else 'Pendiente'}, **Registrador:** {registrador_nombre}, **Confirmador:** {confirmador_nombre if confirmador_nombre else 'Pendiente'}, **Estado:** {estado}")

def listar_empleados():
    cursor.execute('SELECT id, nombre, rol, porcentaje_ganancia FROM empleados')
    empleados = cursor.fetchall()
    if not empleados:
        st.info("No hay empleados registrados.")
        return
    st.subheader("Listado de Empleados:")
    for id_empleado, nombre, rol, porcentaje_ganancia in empleados:
        st.write(f"**ID:** {id_empleado}, **Nombre:** {nombre}, **Rol:** {rol}, **Ganancia:** {porcentaje_ganancia:.2f}%")

def obtener_empleado_por_id(empleado_id):
    cursor.execute('SELECT id, nombre, rol, porcentaje_ganancia FROM empleados WHERE id = ?', (empleado_id,))
    empleado = cursor.fetchone()
    return empleado

def mostrar_historial_ediciones(transferencia_id):
    cursor.execute('''
        SELECT he.fecha_edicion, e.nombre, he.campo_editado, he.valor_anterior, he.valor_nuevo
        FROM historial_ediciones he
        JOIN empleados e ON he.empleado_editor_id = e.id
        WHERE he.transferencia_id = ?
        ORDER BY he.fecha_edicion DESC
    ''', (transferencia_id,))
    historial = cursor.fetchall()
    if not historial:
        st.info(f"No hay historial de ediciones para la Transferencia ID {transferencia_id}.")
        return
    st.subheader(f"Historial de Ediciones para la Transferencia ID {transferencia_id}")
    for fecha_edicion, nombre_editor, campo_editado, valor_anterior, valor_nuevo in historial:
        st.write(f"**Fecha:** {fecha_edicion}, **Editor:** {nombre_editor}, **Campo:** {campo_editado}, **Anterior:** {valor_anterior}, **Nuevo:** {valor_nuevo}")

def mostrar_inventario_mensual(mes, anio):
    """
    Muestra el inventario mensual de dinero enviado y ganancias de los empleados.

    Args:
        mes: El mes para el que se genera el inventario (1-12).
        anio: El año para el que se genera el inventario.
    """
    try:
        fecha_inicio = datetime.date(anio, mes, 1)
        fecha_fin = fecha_inicio + datetime.timedelta(days=32)
        fecha_fin = fecha_fin.replace(day=1) - datetime.timedelta(days=1)
    except ValueError:
        st.error("Por favor, ingrese un mes y año válidos.")
        return

    cursor.execute('''
        SELECT SUM(capital)
        FROM transferencias
        WHERE estado = 'entregada' AND fecha_solicitud BETWEEN ? AND ?
    ''', (fecha_inicio, fecha_fin))
    total_capital = cursor.fetchone()[0] or 0

    ganancia_general_mes = calcular_ganancia_general(total_capital)

    st.subheader(f"Inventario Mensual - {fecha_inicio.strftime('%B %Y')}")
    st.write(f"**Total de capital enviado:** {total_capital:.2f}")
    st.write(f"**Ganancia General del Mes:** {ganancia_general_mes:.2f}")

def mostrar_reporte_ganancias(mes=None, anio=None):
    """Muestra un reporte de ganancias para un mes y año específicos"""
    if mes is None:
        mes = datetime.datetime.now().month
    if anio is None:
        anio = datetime.datetime.now().year
    
    st.subheader(f"Reporte de Ganancias - {mes}/{anio}")
    
    # Total de ganancias generales del mes
    cursor.execute('''
        SELECT SUM(ganancia_general) 
        FROM ganancias_globales 
        WHERE mes = ? AND anio = ?
    ''', (mes, anio))
    total_ganancia_general = cursor.fetchone()[0] or 0
    st.write(f"**Total ganancia general del mes:** ${total_ganancia_general:,.2f}")
    
    # Ganancias por empleado
    cursor.execute('''
        SELECT e.id, e.nombre, e.rol, 
               SUM(g.ganancia_general) as total_gg,
               SUM(g.ganancia_personalizada) as total_gp,
               SUM(g.total_ganancia) as total
        FROM empleados e
        JOIN ganancias_globales g ON e.id = g.empleado_id
        WHERE g.mes = ? AND g.anio = ?
        GROUP BY e.id, e.nombre, e.rol
        ORDER BY total DESC
    ''', (mes, anio))
    
    resultados = cursor.fetchall()
    
    if not resultados:
        st.info("No hay registros de ganancias para este período.")
        return
    
    st.write("**Desglose por empleado:**")
    for emp_id, nombre, rol, gg, gp, total in resultados:
        st.write(f"- **{nombre}** ({rol}):")
        st.write(f"  - Ganancia general: ${gg:,.2f}")
        st.write(f"  - Ganancia personalizada: ${gp:,.2f}")
        st.write(f"  - **Total:** ${total:,.2f}")
        st.write("")

# Crear las tablas al iniciar el programa
crear_tablas()

# Verificar si hay empleados registrados
if not hay_empleados_registrados():
    registrar_primer_administrador()
    st.stop()  # Detener la ejecución hasta que se registre un admin

st.title("Gestión de Transferencias")

# Inicializar el estado de la sesión para el login
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'empleado_id' not in st.session_state:
    st.session_state['empleado_id'] = None
if 'rol' not in st.session_state:
    st.session_state['rol'] = None

# Barra lateral para la autenticación y el menú
with st.sidebar:
    if not st.session_state['logged_in']:
        st.subheader("Iniciar Sesión")
        empleado_id_login = st.number_input("Ingrese su ID de empleado:", step=1, format="%d")
        if st.button("Iniciar Sesión"):
            empleado = obtener_empleado_por_id(empleado_id_login)
            if empleado:
                st.session_state['empleado_id'] = empleado[0]
                st.session_state['rol'] = empleado[2]
                st.session_state['logged_in'] = True
                st.success(f"Bienvenido, {empleado[1]} ({empleado[2]}).")
                st.rerun() # Volver a ejecutar para mostrar el menú
            else:
                st.error("ID de empleado no encontrado.")
    else:
        st.subheader(f"Bienvenido, ID: {st.session_state['empleado_id']}")
        if st.button("Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.session_state['empleado_id'] = None
            st.session_state['rol'] = None
            st.rerun() # Volver a ejecutar para mostrar la pantalla de inicio de sesión

# Contenido principal basado en el rol y la sesión
if not st.session_state['logged_in']:
    st.info("Por favor, inicie sesión en la barra lateral.")
elif st.session_state['rol'] == 'administrador':
    st.subheader("Menú Administrador")
    opcion_admin = st.radio(
        "Seleccione una opción:",
        ["Agregar Empleado", "Listar Empleados", "Listar Transferencias",
         "Mostrar Reporte de Ganancias", "Ver Historial de Ediciones",
         "Mostrar Inventario Mensual"]
    )
    if opcion_admin == "Agregar Empleado":
        st.subheader("Agregar Nuevo Empleado")
        id_empleado_nuevo = st.number_input("ID del empleado:", step=1, format="%d")
        nombre_nuevo = st.text_input("Nombre del empleado:")
        rol_nuevo = st.selectbox("Rol del empleado:", ["administrador", "registrador", "confirmador"])
        porcentaje_nuevo = st.number_input("Porcentaje de ganancia (%):", min_value=0.0, max_value=100.0, step=0.01)
        if st.button("Agregar"):
            cursor.execute('SELECT id FROM empleados WHERE id = ?', (id_empleado_nuevo,))
            existing_id = cursor.fetchone()
            if existing_id:
                st.error("Error: El ID ya existe. Por favor, elija un ID diferente.")
            else:
                agregar_empleado(id_empleado_nuevo, nombre_nuevo, rol_nuevo, porcentaje_nuevo)
    elif opcion_admin == "Listar Empleados":
        listar_empleados()
    elif opcion_admin == "Listar Transferencias":
        listar_transferencias(st.session_state['rol'])
    elif opcion_admin == "Mostrar Reporte de Ganancias":
        st.subheader("Reporte de Ganancias")
        col1, col2 = st.columns(2)
        with col1:
            mes_reporte = st.number_input("Mes:", min_value=1, max_value=12, value=datetime.datetime.now().month)
        with col2:
            anio_reporte = st.number_input("Año:", min_value=2020, max_value=2100, value=datetime.datetime.now().year)
        
        if st.button("Generar Reporte"):
            mostrar_reporte_ganancias(mes_reporte, anio_reporte)
    elif opcion_admin == "Ver Historial de Ediciones":
        transferencia_id_historial = st.number_input("Ingrese el ID de la transferencia para ver su historial de ediciones:", step=1, format="%d")
        mostrar_historial_ediciones(transferencia_id_historial)
    elif opcion_admin == "Mostrar Inventario Mensual":
        mes = st.number_input("Ingrese el mes para el inventario (1-12):", min_value=1, max_value=12, step=1)
        anio = st.number_input("Ingrese el año para el inventario:", step=1, format="%d")
        mostrar_inventario_mensual(mes, anio)

elif st.session_state['rol'] == 'registrador':
    st.subheader("Menú Registrador")
    opcion_registrador = st.radio(
        "Seleccione una opción:",
        ["Registrar Transferencia", "Editar Transferencia", "Listar Mis Transferencias", "Ver Historial de Ediciones"]
    )
    if opcion_registrador == "Registrar Transferencia":
        st.subheader("Registrar Nueva Transferencia")
        remitente_nombre = st.text_input("Nombre del remitente:")
        destinatario_nombre = st.text_input("Nombre del destinatario:")
        destinatario_telefono = st.text_input("Teléfono del destinatario:")
        capital = st.number_input("Capital enviado:", min_value=0.01)
        if st.button("Registrar"):
            # Validar que los campos requeridos no estén vacíos
            if not remitente_nombre:
                st.error("Por favor, ingrese el nombre del remitente.")
            elif not destinatario_nombre:
                st.error("Por favor, ingrese el nombre del destinatario.")
            elif not destinatario_telefono:
                st.error("Por favor, ingrese el teléfono del destinatario.")
            elif capital <= 0:
                st.error("Por favor, ingrese un monto válido mayor que cero.")
            else:
                registrar_transferencia(st.session_state['empleado_id'], remitente_nombre, destinatario_nombre, destinatario_telefono, capital)
    elif opcion_registrador == "Editar Transferencia":
        st.subheader("Editar Transferencia")
        transferencia_id_editar = st.number_input("Ingrese el ID de la transferencia a editar:", step=1, format="%d")
        campo_editar = st.selectbox("Campo a editar:", ['remitente_nombre', 'destinatario_nombre', 'destinatario_telefono', 'capital'])
        nuevo_valor = st.text_input(f"Ingrese el nuevo valor para {campo_editar}:")
        if st.button("Editar"):
            editar_transferencia(transferencia_id_editar, st.session_state['empleado_id'], campo_editar, nuevo_valor)
    elif opcion_registrador == "Listar Mis Transferencias":
        listar_transferencias(st.session_state['rol'], st.session_state['empleado_id'])
    elif opcion_registrador == "Ver Historial de Ediciones":
        transferencia_id_historial = st.number_input("Ingrese el ID de la transferencia para ver su historial de ediciones:", step=1, format="%d")
        mostrar_historial_ediciones(transferencia_id_historial)

elif st.session_state['rol'] == 'confirmador':
    st.subheader("Menú Confirmador")
    opcion_confirmador = st.radio(
        "Seleccione una opción:",
        ["Listar Transferencias Pendientes", "Confirmar Transferencia Entregada"]
    )
    if opcion_confirmador == "Listar Transferencias Pendientes":
        listar_transferencias(st.session_state['rol'], st.session_state['empleado_id'])
    elif opcion_confirmador == "Confirmar Transferencia Entregada":
        st.subheader("Confirmar Entrega de Transferencia")
        listar_transferencias(st.session_state['rol'], st.session_state['empleado_id']) # Mostrar las transferencias pendientes
        transferencia_id_confirmar = st.number_input("ID de la transferencia a confirmar como entregada:", step=1, format="%d")
        if st.button("Confirmar Entrega"):
            confirmar_transferencia_entregada(transferencia_id_confirmar, st.session_state['empleado_id'])

# Cerrar la conexión a la base de datos al finalizar (Streamlit maneja el ciclo de vida de la app, pero es buena práctica)
conn.close()
