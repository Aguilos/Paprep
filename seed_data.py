"""
seed_data.py — Populate PaPrep database with sample data.
Run once after initializing the database:
    python seed_data.py
"""
from datetime import timedelta
from utils import today_pht


def seed(app, db):
    from models import (
        Symptom, LearningModule, Clinic, ClinicSchedule, TimeSlot
    )

    # ── Symptoms ────────────────────────────────────────────────────────────
    if Symptom.query.count() == 0:
        symptoms = [
            # Fever (sort 1x)
            Symptom(name='Mild Fever (37.5°C - 38.5°C)', category='fever',
                    icon='bi-thermometer-half',
                    description='Body temperature between 37.5 °C and 38.5 °C (99.5 °F – 101.3 °F).',
                    sort_order=10),
            Symptom(name='High Fever (above 38.5°C)', category='fever',
                    icon='bi-thermometer-high',
                    description='Body temperature above 38.5 °C (101.3 °F). For infants under 3 months, any fever requires emergency evaluation.',
                    sort_order=11),
            Symptom(name='Chills & Shivering', category='fever',
                    icon='bi-snow2',
                    description='Uncontrollable shaking or shivering sensation, often accompanying fever.',
                    sort_order=12),

            # Respiratory (sort 2x)
            Symptom(name='Cough', category='respiratory',
                    icon='bi-lungs',
                    description='Persistent or frequent coughing episodes.',
                    sort_order=20),
            Symptom(name='Runny Nose', category='respiratory',
                    icon='bi-droplet',
                    description='Nasal discharge (clear or coloured).',
                    sort_order=21),
            Symptom(name='Nasal Congestion', category='respiratory',
                    icon='bi-dash-circle',
                    description='Stuffy or blocked nose making breathing through the nose difficult.',
                    sort_order=22),
            Symptom(name='Difficulty Breathing', category='respiratory',
                    icon='bi-exclamation-triangle-fill',
                    description='Labored, rapid, or difficult breathing; shortness of breath; nostrils flaring. EMERGENCY.',
                    is_emergency=True, sort_order=23),
            Symptom(name='Wheezing', category='respiratory',
                    icon='bi-wind',
                    description='High-pitched whistling sound when the child breathes out.',
                    sort_order=24),
            Symptom(name='Sore Throat', category='respiratory',
                    icon='bi-emoji-frown',
                    description='Pain, scratchiness, or irritation in the throat, often worse when swallowing.',
                    sort_order=25),

            # Digestive (sort 3x)
            Symptom(name='Vomiting', category='digestive',
                    icon='bi-arrow-down-circle',
                    description='Forceful emptying of stomach contents through the mouth.',
                    sort_order=30),
            Symptom(name='Diarrhea', category='digestive',
                    icon='bi-water',
                    description='Loose or watery stools occurring more than 3 times per day.',
                    sort_order=31),
            Symptom(name='Stomach Pain / Cramping', category='digestive',
                    icon='bi-bandaid',
                    description='Pain, cramping, or discomfort in the abdomen.',
                    sort_order=32),
            Symptom(name='Loss of Appetite', category='digestive',
                    icon='bi-cup-hot',
                    description='Noticeably reduced interest in eating or drinking.',
                    sort_order=33),
            Symptom(name='Bloating / Gas', category='digestive',
                    icon='bi-balloon',
                    description='Abdominal distension or excessive intestinal gas.',
                    sort_order=34),

            # Skin (sort 4x)
            Symptom(name='Skin Rash', category='skin',
                    icon='bi-stars',
                    description='Red, itchy, or raised patches on the skin.',
                    sort_order=40),
            Symptom(name='Hives / Allergic Skin Reaction', category='skin',
                    icon='bi-exclamation-circle',
                    description='Raised, itchy welts that appear suddenly — may indicate an allergic reaction.',
                    sort_order=41),
            Symptom(name='Jaundice (Yellow Skin/Eyes)', category='skin',
                    icon='bi-circle-fill',
                    description='Yellowing of the skin or the whites of the eyes.',
                    sort_order=42),
            Symptom(name='Pale Skin', category='skin',
                    icon='bi-circle',
                    description='Unusually light, white, or grayish skin colouration.',
                    sort_order=43),

            # Eyes & Ears (sort 5x)
            Symptom(name='Eye Discharge / Pink Eye', category='eyes_ears',
                    icon='bi-eye',
                    description='Discharge, redness, or crustiness in one or both eyes.',
                    sort_order=50),
            Symptom(name='Ear Pain', category='eyes_ears',
                    icon='bi-ear',
                    description='Pain or discomfort in one or both ears; child may tug at ear.',
                    sort_order=51),

            # Behavioral / Neurological (sort 6x)
            Symptom(name='Excessive / Inconsolable Crying', category='behavioral',
                    icon='bi-emoji-tear',
                    description='Prolonged crying that cannot be soothed despite normal comfort measures.',
                    sort_order=60),
            Symptom(name='Lethargy / Weakness', category='behavioral',
                    icon='bi-battery-low',
                    description='Unusual tiredness, difficulty waking, or noticeable lack of energy.',
                    sort_order=61),
            Symptom(name='Irritability', category='behavioral',
                    icon='bi-lightning',
                    description='Unusual fussiness, agitation, or inconsolable unhappiness.',
                    sort_order=62),
            Symptom(name='Seizure / Convulsion', category='behavioral',
                    icon='bi-lightning-fill',
                    description='Uncontrolled shaking/jerking, muscle stiffness, staring, or brief loss of consciousness. EMERGENCY.',
                    is_emergency=True, sort_order=63),
            Symptom(name='Poor Feeding / Refuses to Eat', category='behavioral',
                    icon='bi-cup-straw',
                    description='Difficulty feeding or refusing breast milk, formula, or food.',
                    sort_order=64),

            # General (sort 7x)
            Symptom(name='Swollen Lymph Nodes', category='general',
                    icon='bi-dot',
                    description='Swollen or tender lumps in the neck, armpits, or groin.',
                    sort_order=70),
        ]
        db.session.add_all(symptoms)
        db.session.commit()
        print(f'  ✓ Seeded {len(symptoms)} symptoms.')

    # ── Learning Modules ─ (seeding removed; modules are managed via /modules/manage) ──

  
    # ── Clinics ─────────────────────────────────────────────────────────────
    if Clinic.query.count() == 0:
        clinics_data = [
            # ── Siniloan, Laguna ─────────────────────────────────────────────
            dict(name='Siniloan District Hospital',
                 address='National Road, Poblacion, Siniloan, Laguna',
                 city='Siniloan', phone='(049) 813-0011',
                 email='siniloan.dh@doh.gov.ph', website='',
                 latitude=14.4274, longitude=121.4479,
                 clinic_type='general', accepts_special_needs=True,
                 description='Government district hospital in Siniloan, Laguna providing general and pediatric healthcare services including developmental assessments and SPED referrals.'),
            dict(name='Rural Health Unit (RHU) Siniloan',
                 address='Municipal Compound, Siniloan, Laguna',
                 city='Siniloan', phone='(049) 813-0022',
                 email='rhu.siniloan@lgulaguna.com', website='',
                 latitude=14.4268, longitude=121.4465,
                 clinic_type='general', accepts_special_needs=False,
                 description='Primary healthcare facility offering maternal and child health services, immunisation, and well-baby clinics for children aged 0–5 in Siniloan.'),
            dict(name='St. Joseph Pediatric & Family Clinic',
                 address='Rizal St, Siniloan, Laguna',
                 city='Siniloan', phone='(049) 813-0055',
                 email='stjoseph.siniloan@gmail.com', website='',
                 latitude=14.4281, longitude=121.4491,
                 clinic_type='pediatric', accepts_special_needs=True,
                 description='Private pediatric and family clinic in Siniloan staffed by a board-certified pediatrician, offering well-child visits, developmental screening, and early intervention referrals.'),
            dict(name='Siniloan Child Wellness Center',
                 address='Brgy. Macatad, Siniloan, Laguna',
                 city='Siniloan', phone='(049) 813-0088',
                 email='childwellness.siniloan@gmail.com', website='',
                 latitude=14.4255, longitude=121.4502,
                 clinic_type='specialty', accepts_special_needs=True,
                 description='Dedicated child wellness and developmental centre in Siniloan offering occupational therapy, speech therapy, and behavioral assessments for children with special needs aged 0–5.'),

            # ── Santa Maria, Laguna ──────────────────────────────────────────
            dict(name='Rural Health Unit (RHU) Santa Maria',
                 address='Municipal Hall Compound, Santa Maria, Laguna',
                 city='Santa Maria', phone='(049) 501-0010',
                 email='rhu.santamaria@lgulaguna.com', website='',
                 latitude=14.4743, longitude=121.4383,
                 clinic_type='general', accepts_special_needs=False,
                 description='Primary healthcare unit in Santa Maria, Laguna providing free immunisation, well-baby check-ups, nutrition counselling, and maternal-child health services.'),
            dict(name='Our Lady of Peace Medical Clinic',
                 address='Brgy. San Antonio, Santa Maria, Laguna',
                 city='Santa Maria', phone='(049) 501-0033',
                 email='ourladyofpeace.sm@gmail.com', website='',
                 latitude=14.4751, longitude=121.4397,
                 clinic_type='pediatric', accepts_special_needs=True,
                 description='Private clinic in Santa Maria, Laguna with a resident pediatrician specialising in early childhood health, developmental monitoring, and special needs support for children 0–5 years.'),
            dict(name='Santa Maria Barangay Health Center',
                 address='Brgy. Poblacion, Santa Maria, Laguna',
                 city='Santa Maria', phone='(049) 501-0044',
                 email='bhc.santamaria@gmail.com', website='',
                 latitude=14.4738, longitude=121.4370,
                 clinic_type='general', accepts_special_needs=False,
                 description='Community health centre providing basic pediatric consultations, growth monitoring, and routine vaccinations for infants and young children in Santa Maria.'),
        ]

        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for cd in clinics_data:
            clinic = Clinic(**cd)
            db.session.add(clinic)
            db.session.flush()  # get clinic.id

            # Standard schedules
            for day in days_order:
                is_sunday = day == 'Sunday'
                is_saturday = day == 'Saturday'
                sched = ClinicSchedule(
                    clinic_id=clinic.id,
                    day_of_week=day,
                    open_time='08:00' if not is_saturday else '09:00',
                    close_time='17:00' if not is_saturday else '13:00',
                    is_closed=is_sunday,
                )
                db.session.add(sched)

            # Generate time slots for next 14 days
            today = today_pht()
            for offset in range(1, 15):
                slot_date = today + timedelta(days=offset)
                weekday_name = slot_date.strftime('%A')
                if weekday_name == 'Sunday':
                    continue
                for start_h, end_h in [('09:00', '09:30'), ('09:30', '10:00'),
                                        ('10:00', '10:30'), ('10:30', '11:00'),
                                        ('11:00', '11:30'), ('13:00', '13:30'),
                                        ('13:30', '14:00'), ('14:00', '14:30'),
                                        ('14:30', '15:00'), ('15:00', '15:30')]:
                    import random
                    booked = random.randint(0, 8)
                    ts = TimeSlot(
                        clinic_id=clinic.id,
                        slot_date=slot_date,
                        start_time=start_h,
                        end_time=end_h,
                        total_slots=10,
                        booked_slots=booked,
                    )
                    db.session.add(ts)

        db.session.commit()
        print(f'  ✓ Seeded {len(clinics_data)} clinics with schedules and time slots.')


if __name__ == '__main__':
    from app import create_app, db as _db
    _app = create_app()
    with _app.app_context():
        _db.create_all()
        print('Seeding database...')
        seed(_app, _db)
        print('Done!')
