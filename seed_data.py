"""Optional local demo seeding for current PaPrep content."""

from datetime import timedelta
from utils import today_pht


def seed(app, db):
    from models import (
        ParentChildResource, Clinic, ClinicSchedule, TimeSlot,
        User, ChildProfile, ClinicAccount, ClinicRegistration,
        Newsletter, NewsletterMedia,
    )

    with app.app_context():
        if ParentChildResource.query.count() == 0:
            db.session.add_all([
                ParentChildResource(
                    title='UNICEF Parenting Resources',
                    description='Practical guidance for nurturing, play, communication, and positive parenting.',
                    url='https://www.unicef.org/parenting/',
                    resource_type='link',
                    category='parenting',
                    target_age_min_months=0,
                    target_age_max_months=60,
                ),
                ParentChildResource(
                    title='CDC Developmental Milestones',
                    description='Learn what to look for as your child grows and when to discuss concerns with a professional.',
                    url='https://www.cdc.gov/ncbddd/actearly/milestones/',
                    resource_type='link',
                    category='development',
                    target_age_min_months=0,
                    target_age_max_months=60,
                ),
            ])
            db.session.commit()
            print('Seeded optional parent and child resources.')

        if Clinic.query.count() == 0:
            clinics_data = [
                dict(name='Siniloan District Hospital', address='National Road, Poblacion, Siniloan, Laguna', city='Siniloan', phone='(049) 813-0011', email='siniloan.dh@doh.gov.ph', website='', latitude=14.4274, longitude=121.4479, clinic_type='general', accepts_special_needs=True, description='Government district hospital in Siniloan, Laguna providing general and pediatric healthcare services including developmental assessments and SPED referrals.'),
                dict(name='Rural Health Unit (RHU) Siniloan', address='Municipal Compound, Siniloan, Laguna', city='Siniloan', phone='(049) 813-0022', email='rhu.siniloan@lgulaguna.com', website='', latitude=14.4268, longitude=121.4465, clinic_type='general', accepts_special_needs=False, description='Primary healthcare facility offering maternal and child health services, immunisation, and well-baby clinics for children aged 0–5 in Siniloan.'),
                dict(name='St. Joseph Pediatric & Family Clinic', address='Rizal St, Siniloan, Laguna', city='Siniloan', phone='(049) 813-0055', email='stjoseph.siniloan@gmail.com', website='', latitude=14.4281, longitude=121.4491, clinic_type='pediatric', accepts_special_needs=True, description='Private pediatric and family clinic in Siniloan staffed by a board-certified pediatrician, offering well-child visits, developmental screening, and early intervention referrals.'),
                dict(name='Siniloan Child Wellness Center', address='Brgy. Macatad, Siniloan, Laguna', city='Siniloan', phone='(049) 813-0088', email='childwellness.siniloan@gmail.com', website='', latitude=14.4255, longitude=121.4502, clinic_type='specialty', accepts_special_needs=True, description='Dedicated child wellness and developmental centre in Siniloan offering occupational therapy, speech therapy, and behavioral assessments for children with special needs aged 0–5.'),
                dict(name='Rural Health Unit (RHU) Santa Maria', address='Municipal Hall Compound, Santa Maria, Laguna', city='Santa Maria', phone='(049) 501-0010', email='rhu.santamaria@lgulaguna.com', website='', latitude=14.4743, longitude=121.4383, clinic_type='general', accepts_special_needs=False, description='Primary healthcare unit in Santa Maria, Laguna providing free immunisation, well-baby check-ups, nutrition counselling, and maternal-child health services.'),
                dict(name='Our Lady of Peace Medical Clinic', address='Brgy. San Antonio, Santa Maria, Laguna', city='Santa Maria', phone='(049) 501-0033', email='ourladyofpeace.sm@gmail.com', website='', latitude=14.4751, longitude=121.4397, clinic_type='pediatric', accepts_special_needs=True, description='Private clinic in Santa Maria, Laguna with a resident pediatrician specialising in early childhood health, developmental monitoring, and special needs support for children 0–5 years.'),
                dict(name='Santa Maria Barangay Health Center', address='Brgy. Poblacion, Santa Maria, Laguna', city='Santa Maria', phone='(049) 501-0044', email='bhc.santamaria@gmail.com', website='', latitude=14.4738, longitude=121.4370, clinic_type='general', accepts_special_needs=False, description='Community health centre providing basic pediatric consultations, growth monitoring, and routine vaccinations for infants and young children in Santa Maria.'),
            ]
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for clinic_data in clinics_data:
                clinic = Clinic(**clinic_data)
                db.session.add(clinic)
                db.session.flush()
                for day in days_order:
                    db.session.add(ClinicSchedule(clinic_id=clinic.id, day_of_week=day, open_time='09:00' if day == 'Saturday' else '08:00', close_time='13:00' if day == 'Saturday' else '17:00', is_closed=day == 'Sunday'))
                today = today_pht()
                for offset in range(1, 15):
                    slot_date = today + timedelta(days=offset)
                    if slot_date.strftime('%A') == 'Sunday':
                        continue
                    for start_time, end_time in [('09:00', '09:30'), ('09:30', '10:00'), ('10:00', '10:30'), ('10:30', '11:00'), ('11:00', '11:30'), ('13:00', '13:30'), ('13:30', '14:00'), ('14:00', '14:30'), ('14:30', '15:00'), ('15:00', '15:30')]:
                        db.session.add(TimeSlot(clinic_id=clinic.id, slot_date=slot_date, start_time=start_time, end_time=end_time, total_slots=10, booked_slots=0))
            db.session.commit()
            print(f'Seeded {len(clinics_data)} clinics with schedules and time slots.')

        demo_parent = User.query.filter_by(email='demo.parent@example.com').first()
        if not demo_parent:
            demo_parent = User(
                email='demo.parent@example.com',
                first_name='Demo',
                last_name='Parent',
            )
            demo_parent.set_password('parent123')
            db.session.add(demo_parent)
            db.session.flush()

        demo_child = ChildProfile.query.filter_by(
            user_id=demo_parent.id, name='Mia Demo'
        ).first()
        if not demo_child:
            demo_child = ChildProfile(
                user_id=demo_parent.id,
                name='Mia Demo',
                date_of_birth=today_pht().replace(year=today_pht().year - 2),
                gender='female',
            )
            db.session.add(demo_child)
            db.session.flush()

        demo_account = ClinicAccount.query.filter_by(email='demo.clinic@example.com').first()
        if not demo_account:
            demo_account = ClinicAccount(
                email='demo.clinic@example.com',
                contact_name='Dr. Demo Clinic',
            )
            demo_account.set_password('clinic123')
            db.session.add(demo_account)
            db.session.flush()

        demo_clinic = Clinic.query.filter_by(clinic_account_id=demo_account.id).first()
        if not demo_clinic:
            demo_clinic = Clinic(
                name='PaPrep Demo Pediatric Clinic',
                city='Demo City',
                clinic_type='pediatric',
                accepts_special_needs=True,
                description='Demo clinic used for local newsletter development and demonstrations.',
                clinic_account_id=demo_account.id,
            )
            db.session.add(demo_clinic)
            db.session.flush()

        registration = ClinicRegistration.query.filter_by(
            clinic_id=demo_clinic.id,
            user_id=demo_parent.id,
        ).first()
        if not registration:
            registration = ClinicRegistration(
                clinic_id=demo_clinic.id,
                user_id=demo_parent.id,
                child_id=demo_child.id,
            )
            db.session.add(registration)
        elif registration.child_id != demo_child.id:
            registration.child_id = demo_child.id

        db.session.flush()
        demo_newsletters = [
            {
                'title': 'Two-Year Checkup Summary',
                'body': 'Mia is growing well and was happy and engaged throughout today’s checkup. Her language, movement, and social development are on track. Keep bringing questions to each visit so we can support her next stage together.',
                'is_published': True,
                'media': [],
            },
            {
                'title': 'New Skills to Celebrate at Home',
                'body': 'Mia is beginning to combine words and follow two-step directions. Try naming what you see during walks and offer simple choices during play to encourage language and independence.',
                'is_published': True,
                'media': [
                    ('image', 'https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?w=900', 'Play and language practice idea'),
                ],
            },
            {
                'title': 'Making Mealtimes Easier',
                'body': 'Offer one familiar food alongside one new food and let Mia decide how much to eat. Keep water available and continue building a relaxed, screen-free mealtime routine.',
                'is_published': True,
                'media': [
                    ('video', 'https://www.youtube.com/watch?v=1Evwgu369Jw', 'Healthy family routines video'),
                ],
            },
            {
                'title': 'Upcoming Vaccination Reminder',
                'body': 'This is a draft reminder for Mia’s next vaccination review. Please confirm the schedule with the clinic before sharing this update with the family.',
                'is_published': False,
                'media': [],
            },
        ]
        for item in demo_newsletters:
            newsletter = Newsletter.query.filter_by(
                clinic_id=demo_clinic.id,
                child_id=demo_child.id,
                title=item['title'],
            ).first()
            if newsletter:
                continue
            newsletter = Newsletter(
                title=item['title'],
                body=item['body'],
                child_id=demo_child.id,
                clinic_id=demo_clinic.id,
                is_published=item['is_published'],
            )
            newsletter.media.extend([
                NewsletterMedia(
                    media_type=media_type,
                    source=source,
                    caption=caption,
                )
                for media_type, source, caption in item['media']
            ])
            db.session.add(newsletter)

        db.session.commit()
        print('Seeded demo clinic-child registration and newsletter entries.')


if __name__ == '__main__':
    from app import create_app, db
    application = create_app()
    seed(application, db)
