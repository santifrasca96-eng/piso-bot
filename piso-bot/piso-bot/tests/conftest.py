import os

# Perfil de prueba (en producción llega por el secreto PROFILE_YAML).
os.environ["PROFILE_YAML"] = """
name: "Santiago"
age: 30
job: "ingeniero de pista en el campeonato del mundo y el europeo de motociclismo"
move_in: "enero de 2027"
phone: "+34 600 000 000"
extra_room_lines:
  - "Soy una persona tranquila, no fumadora y sin mascotas."
"""
os.environ.pop("TELEGRAM_TOKEN", None)
