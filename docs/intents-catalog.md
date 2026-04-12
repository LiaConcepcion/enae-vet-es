# Catálogo de intenciones — chatbot clínica veterinaria

Catálogo de referencia para diseño de NLU, pruebas y prompts del asistente de la clínica. Cada intención incluye nombre (inglés), descripción y un ejemplo de mensaje del usuario en español.

---

## 1. `greeting`

**Descripción:** El usuario inicia la conversación o saluda sin un trámite concreto todavía.

**Ejemplo de mensaje del usuario:** «Hola, buenos días.»

---

## 2. `scheduling_request`

**Descripción:** El usuario quiere pedir cita, agendar una cirugía o esterilización/castración o avanzar en el flujo de reserva.

**Ejemplo de mensaje del usuario:** «Quiero pedir cita para castrar a mi gato la semana que viene.»

---

## 3. `availability_check`

**Descripción:** El usuario pregunta si hay hueco, disponibilidad o cupo en una fecha concreta (con o sin especie).

**Ejemplo de mensaje del usuario:** «¿Tienen sitio para operar a mi perro el martes 15 de abril?»

---

## 4. `pre_operative_info`

**Descripción:** El usuario pide información general antes de la intervención (preparación, qué llevar, qué esperar) sin centrarse solo en ayuno u horarios.

**Ejemplo de mensaje del usuario:** «¿Qué necesito saber antes de la operación de mi mascota?»

---

## 5. `fasting_rules`

**Descripción:** El usuario pregunta por el ayuno, última comida, agua, horas en ayunas o excepciones por edad o condición.

**Ejemplo de mensaje del usuario:** «¿Cuántas horas antes no puede comer mi perro?»

---

## 6. `drop_off_times`

**Descripción:** El usuario pregunta a qué hora debe traer al paciente, ventana de entrega o llegada a la clínica.

**Ejemplo de mensaje del usuario:** «¿A qué hora tengo que traer a mi gato el día de la cirugía?»

---

## 7. `pick_up_times`

**Descripción:** El usuario pregunta cuándo puede recoger al animal, horario orientativo de salida o recogida tras la intervención.

**Ejemplo de mensaje del usuario:** «¿A qué hora más o menos puedo pasar a recogerlo después de la operación?»

---

## 8. `species_specific_rules`

**Descripción:** El usuario pide normas o diferencias según especie (perro vs gato) en el mismo mensaje o compara ambas.

**Ejemplo de mensaje del usuario:** «¿Es igual el protocolo para perros y para gatos el día de la cirugía?»

---

## 9. `dog_in_heat_rejection`

**Descripción:** El usuario informa de que la perra está en celo o pregunta si pueden operarla en ese estado; la clínica debe explicar aplazamiento según protocolo.

**Ejemplo de mensaje del usuario:** «Mi perra está en celo, ¿pueden operarla igual mañana?»

---

## 10. `blood_work_requirements`

**Descripción:** El usuario pregunta si hace falta analítica, preoperatorio sanguíneo o pruebas previas por edad o especie.

**Ejemplo de mensaje del usuario:** «¿Tengo que traer análisis de sangre antes de la castración?»

---

## 11. `carrier_requirements`

**Descripción:** El usuario pregunta por transportín, jaula, collar, bozal o cómo traer al animal de forma segura.

**Ejemplo de mensaje del usuario:** «¿Puedo traer a mi gato en un bolso o tiene que ser transportín cerrado?»

---

## 12. `multiple_pets_redirection`

**Descripción:** El usuario menciona varias mascotas o quiere gestionar varias intervenciones a la vez; el bot debe orientar a tratar caso por caso o canal humano según política.

**Ejemplo de mensaje del usuario:** «Tengo dos perros y un gato, quiero operarlos todos el mismo día.»

---

## 13. `emergency_redirection`

**Descripción:** El usuario describe urgencia, sangrado, no respira, convulsiones o emergencia; el bot debe derivar a servicio de urgencias o contacto adecuado sin dar diagnóstico.

**Ejemplo de mensaje del usuario:** «Mi perro no para de vomitar sangre, ¿pueden verlo ya?»

---

## 14. `cancellation_policy`

**Descripción:** El usuario pregunta cómo anular, reprogramar, plazos, tasas o política de cancelación de la cita.

**Ejemplo de mensaje del usuario:** «Si cancelo la operación con dos días de antelación, ¿hay penalización?»

---

## 15. `microchip_info`

**Descripción:** El usuario pregunta por microchip, registro, obligatoriedad o si la intervención incluye colocación.

**Ejemplo de mensaje del usuario:** «¿Me ponen el microchip el mismo día de la castración?»

---

## 16. `consent_form`

**Descripción:** El usuario pregunta por el consentimiento informado, firma, documentación o formularios previos a la cirugía.

**Ejemplo de mensaje del usuario:** «¿Dónde firmo el consentimiento para la operación?»

---

## 17. `pricing_inquiry`

**Descripción:** El usuario pregunta precio, presupuesto, coste de la cirugía o lo que incluye el importe.

**Ejemplo de mensaje del usuario:** «¿Cuánto cuesta castrar a un perro de tamaño mediano?»

---

## 18. `post_operative_care`

**Descripción:** El usuario pide cuidados después de la intervención, medicación, puntos, collar isabelino, actividad o alimentación postoperatoria.

**Ejemplo de mensaje del usuario:** «¿Qué cuidados tiene que tener mi gato después de esterilizarlo?»

---

## 19. `human_handoff`

**Descripción:** El usuario pide hablar con una persona, recepción, veterinario o salir del bot hacia atención humana.

**Ejemplo de mensaje del usuario:** «Prefiero hablar con alguien de recepción, ¿me pasáis?»

---

## 20. `farewell`

**Descripción:** El usuario cierra la conversación, agradece o se despide sin nueva petición.

**Ejemplo de mensaje del usuario:** «Vale, muchas gracias, hasta luego.»

---

*Documento orientativo para el caso ENAE; alinear respuestas con `docs/pre-operative-considerations.md` y reglas de negocio vigentes en el repositorio.*
