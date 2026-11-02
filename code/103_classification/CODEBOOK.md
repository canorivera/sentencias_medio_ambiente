# Libro de códigos de términos de búsqueda

Archivo generado desde `codebook.csv` por `103_classify.py`. Para cambiar un término se edita el CSV.

Los patrones se aplican sobre el texto normalizado (minúsculas, sin acentos, espacios colapsados).
`contexto` y `excluir` se buscan a menos de 150 caracteres de cada aparición.
`errores` es el número de letras equivocadas que se toleran por errores de OCR.
Pesos: fuerte = 3, medio = 2, debil = 1, ninguno = 0. El puntaje de una resolución es la suma del peso de cada término distinto encontrado. Los términos de peso ninguno no suman al puntaje: solo se registran.
`capa`: `establecimiento` (lugares con fauna en cautiverio) y `bienestar` (condiciones de los ejemplares y maltrato) alimentan el indicador de cautiverio de `103_classify.py`.
Entre paréntesis en `fuente`: número de resoluciones, de 1,594 con texto embebido, que contenían el término en la exploración inicial.

## Marco legal

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| L01 | Ley General de Vida Silvestre | fuerte |  | 2 | `ley general de vida silvestre` |  |  | lista original | Ley principal en la materia. |
| L02 | LGVS | fuerte |  | 0 | `\bl\.? ?g\.? ?v\.? ?s\b\.?` |  |  | lista original | Siglas de la ley. Poco frecuentes: 9 de 1594 resoluciones con texto las usan. |
| L03 | Reglamento de la Ley General de Vida Silvestre | fuerte |  | 2 | `reglamento de la ley general de vida silvestre` |  |  | variante | Nombre completo del reglamento. |
| L04 | RLGVS | fuerte |  | 0 | `\br\.? ?l\.? ?g\.? ?v\.? ?s\b\.?` |  |  | lista original | Siglas del reglamento. |
| L05 | NOM-059-SEMARNAT | fuerte |  | 0 | `nom[- ]?059` |  |  | agregado (184) | Norma de especies en riesgo. |
| L06 | CITES | fuerte |  | 0 | `\bcites\b\|convencion sobre el comercio internacional de especies amenazadas` |  |  | agregado (59) | Convención sobre comercio de especies amenazadas. |
| L07 | Artículo 420 del Código Penal Federal | medio |  | 0 | `\b420\b(?! ?(?:bis\|ter\|quater))` | `codigo penal\|delito\|biodiversidad` |  | agregado (158) | Artículo 420 (fauna). No cuenta 420 Bis/Ter/Quater (humedales, transgénicos, impacto). El número solo cuenta cerca de 'código penal' o 'delito' o 'biodiversidad'. |
| L08 | Delitos contra la biodiversidad | fuerte |  | 1 | `delitos? contra la biodiversidad` |  |  | agregado | Título del Código Penal Federal sobre fauna y flora. |
| L09 | Ley Federal de Sanidad Animal | ninguno | bienestar | 2 | `ley federal de sanidad animal` |  |  | propuesta de investigación (R7) | Obligaciones de alimentación, salud y alojamiento de animales en cautiverio. Citada en la propuesta. |
| L10 | Protección y cuidado de los animales (reforma constitucional 2024) | ninguno | bienestar | 2 | `proteccion y cuidado de los animales\|prohibe (?:el )?maltrato animal` |  |  | propuesta de investigación (R7) | Reforma a los artículos 3, 4 y 73 de la Constitución (DOF 2 de diciembre de 2024). |
| L11 | Ley Federal de Responsabilidad Ambiental | ninguno |  | 2 | `ley federal de responsabilidad ambiental` |  |  | propuesta de investigación (R7) | Aparece en el ejemplo de la propuesta (daño ambiental). Solo se registra. |

## Figuras manejo

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| M01 | Unidad de Manejo para la Conservación de Vida Silvestre | fuerte | establecimiento | 2 | `unidad(?:es)? de manejo para la conservacion de (?:la )?vida silvestre` |  |  | lista original | El nombre legal incluye 'de la'. Se aceptan ambas formas y el plural. |
| M02 | UMA (de manejo) | medio | establecimiento | 0 | `\bu\.? ?m\.? ?a\.? ?s?\b` | `manejo\|conservacion\|silvestre\|registro\|plan de manejo\|aprovechamiento` | `unidad(?:es)? de medida\|valor diario\|veces el valor\|actualizacion` | lista original | Desde 2016 las multas se expresan en UMA (Unidad de Medida y Actualización). Solo cuenta con contexto de manejo y sin contexto de multas. |
| M03 | Predio o Instalación que Maneja Vida Silvestre | fuerte | establecimiento | 2 | `predios? (?:o instalacion(?:es)? )?que manejan? vida silvestre` |  |  | lista original | Nombre legal de PIMVS. |
| M04 | PIMVS | fuerte | establecimiento | 0 | `\bp\.? ?i\.? ?m\.? ?v\.? ?s\b\.?` |  |  | lista original | Siglas. |
| M05 | Zoológico | fuerte | establecimiento | 1 | `zoologicos?` |  |  | lista original |  |
| M06 | Acuario | medio | establecimiento | 0 | `acuarios?` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre\|peces\|marin` | `(?:restaurante\|hotel\|bar\|marisqueria\|plaza\|calle\|avenida\|colonia\|fraccionamiento) (?:el \|la )?acuario` | lista original | Solo cuenta cerca de términos de animales y no cuando es nombre de un negocio o lugar (p. ej. 'restaurante El Acuario'). |
| M07 | Delfinario | fuerte | establecimiento | 1 | `delfinarios?` |  |  | agregado |  |
| M08 | Circo | medio | establecimiento | 0 | `\bcircos?\b` | `animal\|ejemplar\|fauna\|silvestre\|espectaculo` |  | agregado (12) | La LGVS prohíbe ejemplares en circos. Solo cuenta con contexto de animales. |
| M09 | Colección privada | medio | establecimiento | 1 | `colecci(?:on\|ones) privadas?` |  |  | agregado |  |
| M10 | Criadero | medio | establecimiento | 1 | `criaderos?` |  |  | agregado |  |
| M11 | CIVS (siglas) | fuerte |  | 0 | `\bc\.? ?i\.? ?v\.? ?s\b\.?` |  |  | agregado | Centros donde se depositan ejemplares asegurados. Siglas sin tolerancia a errores. |
| M12 | Plan de manejo | debil |  | 1 | `planes? de manejo` |  |  | agregado | También existe en materia forestal. |
| M13 | Centro para la Conservación e Investigación de la Vida Silvestre | fuerte |  | 2 | `centros? para la conservacion e investigacion de (?:la )?vida silvestre` |  |  | agregado | Nombre completo de los CIVS. |

## Establecimientos

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| E01 | Exhibición de animales | ninguno | establecimiento | 0 | `(?:fines? de\|para su\|para la) exhibicion\|exhibicion (?:de\|al) (?:los \|las )?(?:ejemplares\|animales\|fauna\|publico)\|exhibidor(?:es)?` |  |  | propuesta de investigación (R7) | Exhibición en sentido de mostrar animales. 'Exhibición' sola casi siempre es la exhibición de documentos. |
| E02 | Zoo y bioparque | ninguno | establecimiento | 0 | `\bzoo\b\|bioparques?\|\bsafaris?\b` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre\|parque` |  | propuesta de investigación (R7) | Variantes de zoológico. |
| E03 | Aviario, herpetario, serpentario, mariposario | ninguno | establecimiento | 0 | `aviarios?\|herpetarios?\|serpentarios?\|mariposarios?\|reptilarios?` |  |  | propuesta de investigación (R7) | Exhibiciones especializadas. Sin tolerancia a errores: con un error 'aviario' coincide con 'ferroviarios'. |
| E04 | Santuario, refugio o centro de rescate | ninguno | establecimiento | 0 | `santuarios?\|refugios? (?:de\|para) animales\|centros? de (?:rescate\|rehabilitacion)` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre\|rescate\|rehabilitacion` | `area natural protegida\|categoria de santuario\|santuario de (?:la\|las\|los\|el)? ?(?:ballena\|playa\|tortuga marina)\|servicios ambientales\|captura de carbono\|belleza escenica` | propuesta de investigación (R7) | Solo cuenta cerca de animales. 'Santuario' también es categoría de área natural protegida y 'refugio de fauna' aparece en textos forestales sobre servicios ambientales. |
| E05 | Tienda o comercializadora de animales | ninguno | establecimiento | 0 | `tiendas? de (?:mascotas\|animales)\|comercializadoras? de (?:mascotas\|animales\|fauna\|ejemplares)\|venta de (?:mascotas\|animales\|ejemplares)` |  |  | propuesta de investigación (R7) | Venta de fauna en establecimientos. |
| E06 | Espectáculo con animales | ninguno | establecimiento | 0 | `espectaculos? (?:con\|de) (?:animales\|ejemplares\|fauna)\|espectaculos? publicos?` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Espectáculos y ferias con fauna. |
| E07 | Cautiverio o confinamiento | ninguno | establecimiento | 0 | `(?:en\|de) cautiverio\|confinamiento\|confinad[oa]s?\|manejo intensivo` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Describe ejemplares mantenidos en cautiverio. 'Manejo intensivo' es la UMA con ejemplares confinados. No incluye 'fuera de su hábitat natural', que aparece en el párrafo general sobre legal procedencia. |
| E08 | UMA en vida libre (manejo extensivo) | ninguno |  | 1 | `manejo (?:en )?vida libre\|manejo extensivo\|en vida libre` |  |  | propuesta de investigación (R7) | Las UMA de manejo extensivo trabajan con ejemplares en vida libre, no en cautiverio. Se registra para distinguirlas; no forma parte del indicador de cautiverio. |

## Fauna

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| F01 | Vida silvestre | fuerte |  | 1 | `vida silvestre` |  | `forestales,? de (?:la )?vida silvestre,? quelonios\|aprovechamiento sustentable de la vida silvestre y su habitat en zonas que no sean` | variante | Término general de la ley. 198 de 1594 resoluciones con texto. No cuenta dentro de los párrafos de competencia que repiten casi todas las resoluciones ('recursos forestales, de vida silvestre, quelonios...'). |
| F02 | Fauna silvestre | fuerte |  | 1 | `fauna silvestre` |  | `especies nativas de mexico de flora y fauna\|categorias de riesgo y especificaciones\|lista de especies en riesgo` | lista original | 222 de 1594 resoluciones con texto. No cuenta dentro del título de la NOM-059, que ya suma por L05. |
| F03 | Flora silvestre | medio |  | 1 | `flora silvestre` |  | `especies nativas de mexico de flora y fauna\|categorias de riesgo y especificaciones\|lista de especies en riesgo` | agregado (58) | No cuenta dentro del título de la NOM-059, que ya suma por L05. |
| F04 | Ejemplares de vida silvestre | fuerte |  | 2 | `ejemplar(?:es)? de (?:la )?(?:vida\|fauna\|flora) silvestre` |  |  | lista original |  |
| F05 | Ejemplares (con contexto) | debil |  | 0 | `\bejemplar(?:es)?\b` | `fauna\|especie\|silvestre\|\baves?\b\|mamifer\|reptil\|anfibi\|animal\|vivos?\b` | `ejemplar(?:es)? de (?:la\|esta\|dicha) (?:presente )?(?:resolucion\|acuerdo\|oficio)\|en (?:dos\|tres\|un) ejemplar\|forestal\|arbol\|madera\|arbolado` | lista original | Muy frecuente (258 de 1594) y también se usa para árboles y copias de documentos. Solo cuenta junto a términos de fauna. |
| F06 | Especie en riesgo | fuerte |  | 1 | `especies? (?:en riesgo\|amenazadas?\|en peligro de extincion\|sujetas? a proteccion especial\|probablemente extintas?)` |  | `especies nativas de mexico de flora y fauna\|categorias de riesgo y especificaciones\|lista de especies en riesgo` | agregado (96) | Categorías de la NOM-059. No cuenta dentro del título de la NOM-059, que ya suma por L05. |
| F07 | Especie endémica | debil |  | 1 | `especies? endemicas?` |  |  | agregado |  |
| F08 | Especies exóticas o invasoras | medio |  | 1 | `especies? (?:exoticas?\|invasoras?)` |  |  | agregado |  |
| F09 | Mascota | debil |  | 0 | `mascotas?` |  |  | agregado (26) |  |
| F10 | Especies emblemáticas | medio |  | 0 | `\b(?:totoaba\|vaquita marina\|tortugas? marinas?\|psitacid\w*\|guacamayas?\|pericos?\|loros?\|jaguar(?:es)?\|ocelotes?\|primates?\|monos? arana\|cocodril\w*\|caiman(?:es)?\|venados?\|borrego cimarron\|tiburon(?:es)?\|ajolotes?\|aguila real\|halcon(?:es)?)\b` |  |  | agregado | Especies frecuentes en tráfico y protección. Cuenta una vez aunque aparezcan varias. |

## Acciones

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| A01 | Legal procedencia | medio |  | 1 | `legal procedencia` |  |  | agregado (268) | También en materia forestal (madera). |
| A02 | Aseguramiento precautorio | debil |  | 1 | `aseguramiento precautorio` |  |  | agregado (82) | Medida común a varias materias. |
| A03 | Decomiso | debil |  | 0 | `decomis[oa]` |  |  | agregado |  |
| A04 | Marcaje | medio |  | 0 | `marcaje\|microchip\|anillos? de identificacion\|\bchip\b` |  |  | agregado (51) | Sistemas de marca de ejemplares. Sin tolerancia a errores: con un error 'chip' coincide con 'Chih' (Chihuahua). |
| A05 | Liberación de ejemplares | medio |  | 1 | `liberaci(?:on\|ones) de (?:los )?ejemplar` |  |  | agregado |  |
| A06 | Depositario | debil |  | 0 | `depositari[oa]` | `ejemplar\|fauna\|silvestre\|animal` |  | agregado | Solo cuenta junto a ejemplares. |
| A07 | Tráfico o comercio ilegal | medio |  | 1 | `(?:trafico\|comercio) ilegal\|trafico de (?:especies\|fauna\|ejemplares)` |  |  | agregado (28) |  |
| A08 | Aprovechamiento extractivo | medio |  | 1 | `aprovechamiento (?:no )?extractivo` |  |  | agregado | Término de la LGVS. |
| A09 | Posesión de ejemplares | medio |  | 1 | `posesion de (?:los )?ejemplar` |  |  | agregado |  |
| A10 | Traslado o reubicación de ejemplares | ninguno |  | 1 | `(?:traslado\|reubicacion\|canalizacion) de (?:los \|las )?(?:ejemplares\|animales\|especimenes)` |  |  | propuesta de investigación (R7) | Medida de protección (categoría de la propuesta). |
| A11 | Clausura | ninguno |  | 0 | `clausura (?:total\|parcial)? ?(?:temporal\|definitiva)?` |  |  | propuesta de investigación (R7) | Sanción o medida de seguridad. Solo se registra. |
| A12 | Medidas correctivas o de seguridad | ninguno |  | 0 | `medidas? (?:correctivas?\|de seguridad\|de urgente aplicacion)` |  |  | propuesta de investigación (R7) | Aparece en casi todas las resoluciones. Solo se registra. |

## Bienestar

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| B01 | Maltrato animal | fuerte | bienestar | 1 | `maltrato animal\|maltrato a (?:los )?(?:animales\|ejemplares)` |  |  | lista original |  |
| B02 | Maltrato | medio | bienestar | 0 | `maltrat[oa]s?` |  |  | lista original | Puede referirse a otras cosas. Peso medio. |
| B03 | Trato digno y respetuoso | fuerte | bienestar | 2 | `trato digno y respetuoso` |  |  | agregado | Término de la LGVS sobre bienestar animal. |
| B04 | Crueldad | medio | bienestar | 0 | `crueldad` | `animal\|ejemplar\|fauna` |  | agregado |  |
| B05 | Bienestar animal | ninguno | bienestar | 1 | `bienestar (?:animal\|de (?:los \|las )?(?:ejemplares\|animales\|especimenes))` |  |  | propuesta de investigación (R7) | Concepto central de la propuesta. |
| B06 | Alimentación e hidratación | ninguno | bienestar | 0 | `aliment(?:o\|os\|acion\|ar\|ados?)\|hidratacion\|agua (?:limpia\|fresca\|suficiente\|potable)\|bebederos?\|comederos?` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Irregularidad de alimentación (categoría de la propuesta). |
| B07 | Atención veterinaria | ninguno | bienestar | 0 | `atencion (?:medica )?veterinaria\|medicos? veterinarios?\|veterinari[oa]s?\|tratamiento medico` |  |  | propuesta de investigación (R7) | Irregularidad de atención veterinaria (categoría de la propuesta). |
| B08 | Alojamiento e instalaciones | ninguno | bienestar | 0 | `alojamiento\|instalaciones\|encierros?\|jaulas?\|albergues?\|recintos?\|espacio (?:suficiente\|adecuado\|reducido)\|hacinamiento\|sombra` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Irregularidad de alojamiento (categoría de la propuesta). Solo cuenta cerca de términos de animales. |
| B09 | Higiene | ninguno | bienestar | 0 | `higiene\|limpieza\|insalubr\w*\|excretas\|heces\|fauna nociva` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Condiciones sanitarias del alojamiento. |
| B10 | Salud y lesiones | ninguno | bienestar | 0 | `lesion(?:es\|ado\|ados)?\|herid[oa]s?\|enferm(?:o\|os\|a\|as\|edad\|edades)\|desnutri\w*\|deshidrat\w*\|condicion corporal\|parasit\w*\|estado de salud` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Daños a la salud de los ejemplares. |
| B11 | Comportamiento y enriquecimiento | ninguno | bienestar | 0 | `estres\|estereotipi\w*\|enriquecimiento ambiental\|conductas? anormal(?:es)?\|comportamiento anormal` |  |  | propuesta de investigación (R7) | Bienestar conductual y psicológico (riesgo 'conductual o psicológico' de la propuesta). Sin errores de OCR: con uno, "estres" aparece en palabras comunes ("e tres", "estre"). |
| B12 | Muerte de ejemplares | ninguno | bienestar | 0 | `muerte\|muri[oe]\|fallec\w*\|necropsias?\|eutanasia\|sacrificio` | `ejemplar\|animal\|fauna\|especie` |  | propuesta de investigación (R7) | Muerte, necropsia o sacrificio de ejemplares. |
| B13 | Abandono y sufrimiento | ninguno | bienestar | 0 | `abandono\|sufrimiento\|dolor innecesario\|descuido\|negligencia` | `ejemplar\|animal\|fauna\|especie\|individuo\|silvestre` |  | propuesta de investigación (R7) | Formas de maltrato por omisión. |

## Procedimiento

| id | término | peso | capa | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|---|
| P01 | Denuncia popular | debil |  | 1 | `denuncia popular` |  |  | lista original | Vía de inicio común a todas las materias. |
| P02 | Denuncia | debil |  | 0 | `denuncias?` |  |  | lista original | Muy general. Solo suma con otros términos. |
| P03 | Dirección de inspección de vida silvestre | fuerte |  | 2 | `inspeccion (?:y vigilancia )?(?:de\|en materia de) vida silvestre` |  |  | agregado | Área de PROFEPA a cargo de la materia. |
