---
layout: page
title: El equipo
lang: es
permalink: /es/equipo/
description: Las personas detrás del TS Pico — Ricardo, Gustavo, Jeff, Tim y David.
---

## Ricardo Calcagno

<img class="portrait" src="{{ '/assets/img/ricardo.jpg' | relative_url }}" alt="Ricardo Calcagno">

Soy Ingeniero en Sistemas, ex docente de la Universidad Tecnológica Nacional y actualmente empresario que vive en Resistencia, ciudad al norte de Argentina.

Mi primera computadora fue una Timex Sinclair 2068, adquirida en 1984. Al vivir lejos de las grandes ciudades de Argentina, las opciones eran limitadas en mi ciudad: la TI-99/4A y la TS, mucho más asequible. Siempre disfruté el enfoque avanzado del TS: las teclas con tokens que evitaban muchos errores tipográficos, la arquitectura relativamente simple, el hardware elegante, hermoso y futurista, la extensa biblioteca de software en cassette relativamente económica que podía conseguir en mi ciudad, los muchos programas para Spectrum que podía tipear desde el principio.

Cuando terminé la escuela secundaria, dejé mi computadora en algún lugar de la casa de mis padres y finalmente la perdí. Más tarde, a finales de los 90, conseguí una barata en Internet. La compré, la guardé y la olvidé por completo nuevamente.

Durante la pandemia, con todo el tiempo del mundo y tratando de encontrar algo para hacer, desempolvé mi TS2068 e intenté jugar algunos juegos antiguos, pero lo que me molestó fue la falta de una solución de almacenamiento nativa adecuada, al estilo del DivIDE/DivMMC para la Spectrum. Investigando en línea, encontré el proyecto PC-ZX del Dr. Beep.

Me preguntaba si sería posible actualizar ese proyecto a estos días, usando una Raspberry Pico, los PIO del Pico y Python en lugar de una PC, el puerto paralelo y Turbo Pascal. Aquel, mi primer proyecto de ese tipo, funcionó y compartí mi progreso con la comunidad. Es el núcleo del actual proyecto TS-Pico, mejorado con las invaluables contribuciones de David, Gustavo, Jeff y Tim (en orden alfabético). Hoy en día, soy responsable del programa principal en Python, incluidas las máquinas de estado (StateMachine) que controlan las E/S hacia y desde la TS.

TS-Pico ha crecido hasta convertirse en una solución mucho mejor y más completa, pero manteniendo su concepto abierto esencial, que le permita al usuario interactuar y “jugar” con el hardware/software de su amada TS2068 de maneras que estoy seguro le resultarán increíbles, creando sus propias rutinas y añadiendo funcionalidades, y compartiéndolas con sus compañeros usuarios.

## Gustavo Pane

<img class="portrait" src="{{ '/assets/img/gustavo.jpg' | relative_url }}" alt="Gustavo Pane">

He tenido la suerte de poder utilizar computadoras Sinclair desde principios de los años 1980. Mi primera computadora fue una Timex Sinclair 2068, obtenida en el año 1984, cuando mi padre me la regaló para usarla en mis estudios de electrónica, justo cuando terminaba la secundaria.

A partir de ese momento, la curva de aprendizaje se volvió exponencial. Comencé a programar en BASIC, usándola para resolver ecuaciones matemáticas, aplicaciones electrónicas, cálculos de circuitos transistorizados y gráficos 2D y 3D.

Siempre preferí centrarme en la programación de bajo nivel, usando lenguaje de máquina, particularmente para el microprocesador Z80. Casi todas mis rutinas y programas desarrollados en la TS-2068 fueron escritos usando Zeus Assembler.

En aquel momento me dedicaba a la programación de BIOS y aplicaciones profesionales para CP/M y MP/M 80 y encontré en la TS2068 una excelente plataforma integrada y fácil de usar para desarrollar sistemas con microprocesadores.

Pronto me di cuenta de que necesitaba un método de almacenamiento para guardar y cargar programas y datos que fuera más rápido y confiable que el sistema de cassettes original. Decidí crear una interfaz para conectar la TS2068 con una computadora más potente que ejecutase CP/M para poder usar un disco duro de 40 MB para almacenar mis programas.

Utilicé mis conocimientos de electrónica y programación, modificando el uso de los comandos SAVE/LOAD originales, pero manteniendo simultáneamente el sistema de cassettes, porque toda mi biblioteca estaba guardada en cinta.

Hoy, 40 años después del lanzamiento del TS2068, encontré útil adaptar mis rutinas de almacenamiento CP/M a la interface TS-Pico, más nueva y avanzada, disponible hoy. Además de la versión original, que solo admitía SAVE/LOAD/VERIFY/MERGE, he incluido los comandos COPY/LPRINT/LLIST para que puedan ser manejados por TS-Pico. Puede guardar archivos de texto o de imagen, destinados a la impresora TS2040, en las tarjetas SD.

Estoy muy orgulloso de ser parte del grupo de cuatro personas que forman este nuevo proyecto, y quiero agradecer públicamente a los demás miembros del equipo, que han ayudado a que mi programa escrito hace 40 años sea parte de esta solución de almacenamiento para la TS2068.

## Jeff Burrell

La primera computadora de Jeff fue una Sinclair ZX-81 que compró mientras estaba en la Fuerza Aérea de EE. UU. estacionada en el Reino Unido. En ese momento, era un técnico que trabajaba en equipos satelitales avanzados de comunicación por microondas y tenía acceso a una minicomputadora Hewlett-Packard con un compilador FORTRAN.

Esto, junto con su experiencia en programación en la universidad, lo llevó a comprar el ZX-81 cuando lo vio anunciado en una revista británica de electrónica. Durante los aproximadamente cinco años que usó esa computadora, aprendió a programar en BASIC y en código de máquina ensamblado a mano y a utilizar al máximo las características y limitaciones del “pequeño tope de puerta negro”.

Mientras estuvo estacionado en Offutt AFB, un compañero de trabajo que estaba pasando a una computadora basada en CP/M desde su TS-2068. Cuando vio el 2068, supo que lo quería. Quedó impresionado por la funcionalidad que Clive Sinclair había logrado incluir en el ZX-81 y, al examinar la documentación de la TS2068, vio que se trataba de una máquina muy prometedora. Compró la máquina y comenzó a programar de inmediato y descubrió, como era de esperar, que había muchas cosas que le gustaban del 2068.

Jeff ha aportado al proyecto su experiencia profesional en el diseño de placas de circuito impreso, adaptando y mejorando el diseño original de Ricardo.

## Tim H

Tim H, a diferencia de los demás miembros del equipo, es un recién llegado a la Timex Sinclair 2068. Al vivir en Nueva Zelanda, las primeras experiencias de Tim con microcomputadoras incluyeron los modelos de Sinclair: el ZX81 y el ZX Spectrum.

En los últimos años, Tim adquirió un TS 2068 y se volvió activo en la comunidad internacional de TS, ayudando a preservar y mejorar el hardware diseñado por entusiastas de TS en el pasado, incluida una placa de captura de video desarrollada por miembros del grupo de usuarios de TS a fines de la década de 1980.

Tim se unió inicialmente al equipo y ofreció su soporte de diseño de software y hardware para el proyecto.

## David Anderson

<img class="portrait" src="{{ '/assets/img/david.png' | relative_url }}" alt="David Anderson (a la derecha)">

Soy la persona detrás de [timexsinclair.com](https://timexsinclair.com) y organizo reuniones regulares de Zoom para otros entusiastas de la TS.

La primera computadora de mi hogar fue la Timex Sinclair 1000, en la que pasé muchas horas aprendiendo y programando. Jugar con mi 1000 toda la noche (algo fácil de hacer cuando era adolescente) era bastante común.

Mis primeras experiencias con muchas computadoras, desde micros domésticas hasta mainframes, me llevaron a una carrera en TI y, finalmente, a desarrollar y administrar sitios web.

A pesar de tener varios sistemas diferentes, mis favoritos siempre han sido el Timex Sinclair 1000 y el 2068. Tengo un 2068 en su escritorio que entra en acción varias veces a la semana.

Cuando Ricardo y Gustavo me contactaron sobre el TS Pico, inmediatamente recomendé a Tim H como posible miembro del equipo. No mucho después, sugerí invitar a Jeff, que estaba trabajando en un proyecto similar, para coordinar esfuerzos y garantizar que los dos proyectos funcionaran juntos. Jeff también se incorporó rápidamente al proyecto TS Pico.

En este proyecto, facilité reuniones semanales del equipo y ayudé a mantener el alcance enfocado en el objetivo del lanzamiento cerca del 40.º aniversario del TS 2068. Estoy trabajando en la guía del usuario y eventualmente haré que el TS Pico esté disponible a través de mi sitio, [andertone.com](https://andertone.com).
