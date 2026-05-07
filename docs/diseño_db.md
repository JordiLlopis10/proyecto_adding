ENTIDAD 1 — Provider

Representa una pasarela de pago.

Campos
Campo	Tipo
id	Integer
name	String
api_key	String
sandbox_mode	Boolean
active	Boolean
created_at	DateTime
ENTIDAD 2 — Transaction

Representa un intento de pago.

Campos
Campo	Tipo
id	Integer
provider_id	FK
amount	Decimal
currency	String
status	String
created_at	DateTime
ENTIDAD 3 — Incident

Representa errores o problemas.

Campos
Campo	Tipo
id	Integer
transaction_id	FK
incident_type	String
description	Text
created_at	DateTime