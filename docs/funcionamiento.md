# DIO CRM — qué es y cómo funciona

DIO CRM es una plataforma comercial para cualquier empresa que venda productos o servicios. Sirve para llevar, en un solo lugar, a quién se le vende, en qué punto está cada negocio y cuánto vale lo que está en curso.

Lo pueden usar empresas de software, consultoras, comercios, distribuidores, agencias y prestadores de servicios. Cada empresa tiene sus propios datos, su propio equipo y su propio proceso de venta. El sistema no asume que todas trabajan igual: las etapas del pipeline y los campos extra se configuran por empresa.

## Para qué sirve

El trabajo comercial suele repartirse entre hojas de cálculo, correos y notas sueltas. DIO CRM junta ese ciclo:

1. Llega un prospecto.
2. Se convierte en una oportunidad dentro de un pipeline.
3. El equipo registra llamadas, tareas y reuniones.
4. Se arma una cotización con el catálogo de la empresa.
5. El panel muestra cuántas oportunidades siguen abiertas y cuánto dinero representan.

La interfaz no decide precios ni estados. Esas reglas viven en el servidor, así todas las empresas ven el mismo resultado para los mismos datos.

## Una instalación, muchas empresas

DIO CRM está preparado para funcionar como producto SaaS. Varias empresas comparten la misma aplicación y la misma base de datos, pero cada una solo ve lo suyo.

Al registrarse, una persona indica el nombre de su empresa, su nombre, un correo y una contraseña. El sistema hace tres cosas:

- Crea la empresa (el tenant) y un identificador único a partir del nombre.
- Crea al primer usuario como propietario (`owner`).
- Crea el pipeline **Comercial**, marcado como predeterminado, con estas etapas:

| Etapa | Probabilidad | Resultado |
| --- | --- | --- |
| Nuevo | 10 % | Abierta |
| Calificación | 30 % | Abierta |
| Propuesta | 50 % | Abierta |
| Negociación | 75 % | Abierta |
| Ganada | 100 % | Ganada |
| Perdida | 0 % | Perdida |

Un administrador puede agregar después otras etapas o otro pipeline. La etapa Ganada cierra la oportunidad como ganada. La etapa Perdida la cierra como perdida. El resto la deja abierta.

## Cómo sabe el sistema de qué empresa se trata

Después del registro o del ingreso, el servidor entrega un token JWT. Ese token incluye quién es el usuario, su rol y la empresa a la que pertenece.

Cada consulta y cada cambio usa esa empresa. No hace falta enviarla en el formulario: si alguien intenta leer o modificar un registro de otra empresa, la API responde **404** (no encontrado). Las relaciones de la base también exigen que la cuenta, el contacto, la etapa o el producto pertenezcan a la misma empresa. Así un dato no puede quedar enlazado con el de un vecino.

## Quién puede hacer qué

| Rol | Para qué existe |
| --- | --- |
| `owner` | Dueño de la empresa. Configura y opera el ciclo comercial. |
| `admin` | Igual que el dueño para la configuración: usuarios, pipelines, etapas y campos personalizados. |
| `sales` | Trabaja el día a día: cuentas, contactos, prospectos, oportunidades, actividades, catálogo y cotizaciones. |
| `viewer` | Solo consulta. Si intenta guardar algo, el servidor responde que no tiene permiso. |

El primer usuario siempre es `owner`. Los siguientes los invita un administrador y no pueden crearse como dueños desde esa pantalla.

## El ciclo comercial

**Cuentas.** Son las empresas o negocios a los que se les vende: nombre, sector, sitio, teléfono, correo y notas.

**Contactos.** Son las personas. Tienen nombre, apellido, cargo, correo, teléfono y, si aplica, la cuenta a la que pertenecen.

**Prospectos.** Son oportunidades todavía sin formalizar. Nacen como nuevos y pueden pasar a contactado, calificado o no calificado. Al convertir uno, el sistema abre una oportunidad en la primera etapa abierta del pipeline predeterminado, la relaciona con ese prospecto y marca al prospecto como convertido. No se puede convertir dos veces.

**Oportunidades.** Son los negocios en curso. Tienen título, importe, moneda, pipeline, etapa y, si se quiere, cuenta, contacto o prospecto. Al moverlas de etapa, el estado sale de esa etapa: abierta, ganada o perdida. Una etapa de otro pipeline no se acepta.

**Actividades.** Son tareas, llamadas y reuniones. Se pueden completar. El panel cuenta las que siguen pendientes.

**Catálogo.** Productos y servicios con nombre, código opcional, precio, moneda y una marca de si es servicio. El código, cuando existe, no se repite dentro de la misma empresa.

**Cotizaciones.** Se emiten contra una cuenta y pueden ligarse a una oportunidad. Cada línea puede tomar un producto del catálogo o describirse a mano. Si la línea tiene producto, el precio lo pone el servidor con el valor actual del catálogo; el precio que envíe la pantalla no se usa. El servidor calcula el importe de la línea, resta el descuento y guarda el subtotal y el total. El descuento no puede superar el importe de la línea y la cantidad tiene que ser mayor que cero. El número sale con la forma `COT-0001`. La cotización nace en borrador y después puede pasar a enviada, aceptada, rechazada o vencida.

**Campos personalizados.** Sirven cuando una empresa necesita un dato que las demás no usan. Un administrador define la entidad (cuenta, contacto, prospecto u oportunidad), la etiqueta, una clave en minúsculas y el tipo de campo. La clave no se repite para la misma entidad dentro de la empresa. Otra empresa puede usar la misma clave sin conflicto.

**Panel.** No es una tabla. Resume, para la empresa del token, cuántas cuentas y contactos hay, cuántos prospectos y oportunidades siguen abiertos, el valor del pipeline abierto, las actividades pendientes y las cotizaciones en borrador o enviadas.

## Dónde viven los datos

PostgreSQL guarda todo. La migración `0002_crm` creó las tablas del CRM: empresas, usuarios, cuentas, contactos, prospectos, pipelines, etapas, oportunidades, actividades, productos, cotizaciones, líneas de cotización, campos personalizados y sus valores.

Los usuarios del CRM están en la tabla `crm_users`. Si en el volumen local de PostgreSQL ya existían tablas de un prototipo anterior, esas tablas siguen ahí y la aplicación no las consulta ni las borra.

## Cómo se usa

La carpeta que contiene `CRM-Back` y `CRM-Front` tiene el archivo `compose.yaml`. Con `docker compose up --build` quedan en marcha la base, la API y nginx.

- La interfaz se abre en http://localhost y en http://localhost:4200.
- Nginx entrega las pantallas y reenvía `/api`, `/health` y `/docs` a la API.
- La API directa sigue en http://localhost:8000.
- PostgreSQL queda publicado en `localhost:5433`.

El primer paso en la interfaz es **Crear empresa**. A partir de ahí el menú lleva al panel, las cuentas, los contactos, los prospectos, las oportunidades, las actividades, el catálogo, las cotizaciones y la configuración.
