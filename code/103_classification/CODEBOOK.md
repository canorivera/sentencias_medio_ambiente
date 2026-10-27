# Libro de códigos de términos de búsqueda

Archivo generado desde `codebook.csv` por `103_classify.py`. Para cambiar un término se edita el CSV.

Los patrones se aplican sobre el texto normalizado (minúsculas, sin acentos, espacios colapsados).
`contexto` y `excluir` se buscan a menos de 150 caracteres de cada aparición.
`errores` es el número de letras equivocadas que se toleran por errores de OCR.
Pesos: fuerte = 3, medio = 2, debil = 1. El puntaje de una resolución es la suma del peso de cada término distinto encontrado.
Entre paréntesis en `fuente`: número de resoluciones, de 1,594 con texto embebido, que contenían el término en la exploración inicial.

## Marco legal

| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|
| L01 | Ley General de Vida Silvestre | fuerte | 2 | `ley general de vida silvestre` |  |  | lista original | Ley principal en la materia. |
| L02 | LGVS | fuerte | 0 | `\bl\.? ?g\.? ?v\.? ?s\b\.?` |  |  | lista original | Siglas de la ley. Poco frecuentes: 9 de 1594 resoluciones con texto las usan. |
| L03 | Reglamento de la Ley General de Vida Silvestre | fuerte | 2 | `reglamento de la ley general de vida silvestre` |  |  | variante | Nombre completo del reglamento. |
| L04 | RLGVS | fuerte | 0 | `\br\.? ?l\.? ?g\.? ?v\.? ?s\b\.?` |  |  | lista original | Siglas del reglamento. |
| L05 | NOM-059-SEMARNAT | fuerte | 0 | `nom[- ]?059` |  |  | agregado (184) | Norma de especies en riesgo. |
| L06 | CITES | fuerte | 0 | `\bcites\b\|convencion sobre el comercio internacional de especies amenazadas` |  |  | agregado (59) | Convención sobre comercio de especies amenazadas. |
| L07 | Artículo 420 del Código Penal Federal | medio | 0 | `\b420\b(?! ?(?:bis\|ter\|quater))` | `codigo penal\|delito\|biodiversidad` |  | agregado (158) | Artículo 420 (fauna). No cuenta 420 Bis/Ter/Quater (humedales, transgénicos, impacto). El número solo cuenta cerca de 'código penal' o 'delito' o 'biodiversidad'. |
| L08 | Delitos contra la biodiversidad | fuerte | 1 | `delitos? contra la biodiversidad` |  |  | agregado | Título del Código Penal Federal sobre fauna y flora. |

## Figuras manejo

| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|
| M01 | Unidad de Manejo para la Conservación de Vida Silvestre | fuerte | 2 | `unidad(?:es)? de manejo para la conservacion de (?:la )?vida silvestre` |  |  | lista original | El nombre legal incluye 'de la'. Se aceptan ambas formas y el plural. |
| M02 | UMA (de manejo) | medio | 0 | `\bu\.? ?m\.? ?a\.? ?s?\b` | `manejo\|conservacion\|silvestre\|registro\|plan de manejo\|aprovechamiento` | `unidad(?:es)? de medida\|valor diario\|veces el valor\|actualizacion` | lista original | Desde 2016 las multas se expresan en UMA (Unidad de Medida y Actualización). Solo cuenta con contexto de manejo y sin contexto de multas. |
| M03 | Predio o Instalación que Maneja Vida Silvestre | fuerte | 2 | `predios? (?:o instalacion(?:es)? )?que manejan? vida silvestre` |  |  | lista original | Nombre legal de PIMVS. |
| M04 | PIMVS | fuerte | 0 | `\bp\.? ?i\.? ?m\.? ?v\.? ?s\b\.?` |  |  | lista original | Siglas. |
| M05 | Zoológico | fuerte | 1 | `zoologicos?` |  |  | lista original |  |
| M06 | Acuario | medio | 0 | `acuarios?` |  |  | lista original | Puede aparecer en domicilios o nombres comerciales. |
| M07 | Delfinario | fuerte | 1 | `delfinarios?` |  |  | agregado |  |
| M08 | Circo | medio | 0 | `\bcircos?\b` | `animal\|ejemplar\|fauna\|silvestre\|espectaculo` |  | agregado (12) | La LGVS prohíbe ejemplares en circos. Solo cuenta con contexto de animales. |
| M09 | Colección privada | medio | 1 | `colecci(?:on\|ones) privadas?` |  |  | agregado |  |
| M10 | Criadero | medio | 1 | `criaderos?` |  |  | agregado |  |
| M11 | CIVS (siglas) | fuerte | 0 | `\bc\.? ?i\.? ?v\.? ?s\b\.?` |  |  | agregado | Centros donde se depositan ejemplares asegurados. Siglas sin tolerancia a errores. |
| M13 | Centro para la Conservación e Investigación de la Vida Silvestre | fuerte | 2 | `centros? para la conservacion e investigacion de (?:la )?vida silvestre` |  |  | agregado | Nombre completo de los CIVS. |
| M12 | Plan de manejo | debil | 1 | `planes? de manejo` |  |  | agregado | También existe en materia forestal. |

## Fauna

| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|
| F01 | Vida silvestre | fuerte | 1 | `vida silvestre` |  | `forestales,? de (?:la )?vida silvestre,? quelonios\|aprovechamiento sustentable de la vida silvestre y su habitat en zonas que no sean` | variante | Término general de la ley. 198 de 1594 resoluciones con texto. No cuenta dentro de los párrafos de competencia que repiten casi todas las resoluciones ('recursos forestales, de vida silvestre, quelonios...'). |
| F02 | Fauna silvestre | fuerte | 1 | `fauna silvestre` |  |  | lista original | 222 de 1594. |
| F03 | Flora silvestre | medio | 1 | `flora silvestre` |  |  | agregado (58) |  |
| F04 | Ejemplares de vida silvestre | fuerte | 2 | `ejemplar(?:es)? de (?:la )?(?:vida\|fauna\|flora) silvestre` |  |  | lista original |  |
| F05 | Ejemplares (con contexto) | debil | 0 | `\bejemplar(?:es)?\b` | `fauna\|especie\|silvestre\|\baves?\b\|mamifer\|reptil\|anfibi\|animal\|vivos?\b` | `ejemplar(?:es)? de (?:la\|esta\|dicha) (?:presente )?(?:resolucion\|acuerdo\|oficio)\|en (?:dos\|tres\|un) ejemplar\|forestal\|arbol\|madera\|arbolado` | lista original | Muy frecuente (258 de 1594) y también se usa para árboles y copias de documentos. Solo cuenta junto a términos de fauna. |
| F06 | Especie en riesgo | fuerte | 1 | `especies? (?:en riesgo\|amenazadas?\|en peligro de extincion\|sujetas? a proteccion especial\|probablemente extintas?)` |  |  | agregado (96) | Categorías de la NOM-059. |
| F07 | Especie endémica | debil | 1 | `especies? endemicas?` |  |  | agregado |  |
| F08 | Especies exóticas o invasoras | medio | 1 | `especies? (?:exoticas?\|invasoras?)` |  |  | agregado |  |
| F09 | Mascota | debil | 0 | `mascotas?` |  |  | agregado (26) |  |
| F10 | Especies emblemáticas | medio | 0 | `\b(?:totoaba\|vaquita marina\|tortugas? marinas?\|psitacid\w*\|guacamayas?\|pericos?\|loros?\|jaguar(?:es)?\|ocelotes?\|primates?\|monos? arana\|cocodril\w*\|caiman(?:es)?\|venados?\|borrego cimarron\|tiburon(?:es)?\|ajolotes?\|aguila real\|halcon(?:es)?)\b` |  |  | agregado | Especies frecuentes en tráfico y protección. Cuenta una vez aunque aparezcan varias. |

## Acciones

| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|
| A01 | Legal procedencia | medio | 1 | `legal procedencia` |  |  | agregado (268) | También en materia forestal (madera). |
| A02 | Aseguramiento precautorio | debil | 1 | `aseguramiento precautorio` |  |  | agregado (82) | Medida común a varias materias. |
| A03 | Decomiso | debil | 0 | `decomis[oa]` |  |  | agregado |  |
| A04 | Marcaje | medio | 0 | `marcaje\|microchip\|anillos? de identificacion\|\bchip\b` |  |  | agregado (51) | Sistemas de marca de ejemplares. Sin tolerancia a errores: con un error 'chip' coincide con 'Chih' (Chihuahua). |
| A05 | Liberación de ejemplares | medio | 1 | `liberaci(?:on\|ones) de (?:los )?ejemplar` |  |  | agregado |  |
| A06 | Depositario | debil | 0 | `depositari[oa]` | `ejemplar\|fauna\|silvestre\|animal` |  | agregado | Solo cuenta junto a ejemplares. |
| A07 | Tráfico o comercio ilegal | medio | 1 | `(?:trafico\|comercio) ilegal\|trafico de (?:especies\|fauna\|ejemplares)` |  |  | agregado (28) |  |
| A08 | Aprovechamiento extractivo | medio | 1 | `aprovechamiento (?:no )?extractivo` |  |  | agregado | Término de la LGVS. |
| A09 | Posesión de ejemplares | medio | 1 | `posesion de (?:los )?ejemplar` |  |  | agregado |  |

## Bienestar

| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|
| B01 | Maltrato animal | fuerte | 1 | `maltrato animal\|maltrato a (?:los )?(?:animales\|ejemplares)` |  |  | lista original |  |
| B02 | Maltrato | medio | 0 | `maltrat[oa]s?` |  |  | lista original | Puede referirse a otras cosas. Peso medio. |
| B03 | Trato digno y respetuoso | fuerte | 2 | `trato digno y respetuoso` |  |  | agregado | Término de la LGVS sobre bienestar animal. |
| B04 | Crueldad | medio | 0 | `crueldad` | `animal\|ejemplar\|fauna` |  | agregado |  |

## Procedimiento

| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |
|---|---|---|---|---|---|---|---|---|
| P01 | Denuncia popular | debil | 1 | `denuncia popular` |  |  | lista original | Vía de inicio común a todas las materias. |
| P02 | Denuncia | debil | 0 | `denuncias?` |  |  | lista original | Muy general. Solo suma con otros términos. |
| P03 | Dirección de inspección de vida silvestre | fuerte | 2 | `inspeccion (?:y vigilancia )?(?:de\|en materia de) vida silvestre` |  |  | agregado | Área de PROFEPA a cargo de la materia. |
