# cargar_historico.py

## Descripción general

Desde tu environment, el script toma la Connection String para poder hacer estos cambios directamente en la base de datos, sin tener que recurrir a un codigo insert masivo en el SQL Editor de forma manual.

## Ejecución

Para ejecutar el script. Lo normal es escribir la siguiente linea en la terminal de tu entorno: "python cargar_historico.py data/maquinas.csv data/matriz.csv"

## Seguridad de los datos

Debido a que la informacion de data es sensible, tenes que asegurarte que todo esto vaya en el .gitignore

## Comportamiento del script

Una vez preparado estos archivos, lo que va a hacer el script es insertar automaticamente todos los registros que sean compatibles con el schema-postgre.sql

### Idempotencia

Esto funciona de manera en que cada ficha tiene su numero de ficha unico, por ende no es posible que se dupliquen datos. Cuando el script detecta que un registro contiene un numero de ficha que ya se encuentra en la base de datos, se marcara en el contador de registros "skipped" el cual aparece como valor de retorno.

### Manejo de errores

Los ingresos que no sean compatibles con el schema, se incluiran en un archivo como "errores_fechacreado.csv", en donde se enlistaran todos los registros con error y su motivo.

### Resolución de errores

La manera en que se podran resolver estos registros con error, es mediante el Product Owner, quien valida y corrige la informacion para poder cargar estos datos nuevamente.