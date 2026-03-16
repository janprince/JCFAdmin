"""
Seed the database with mock data matching the frontend website.
Run:  python manage.py seed_website_data
"""
from datetime import date, time, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import Event, EventCategory
from blog.models import Author, Category, Tag, Post
from causes.models import Cause, CauseCategory, Donation
from centres.models import Centre
from website.models import (
    GalleryItem, VolunteerOpportunity, Testimonial,
    TeamMember, ImpactStat,
)


class Command(BaseCommand):
    help = 'Seed the database with website mock data'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true', help='Delete existing data before seeding')

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('Flushing existing data...')
            for model in [
                Donation, ImpactStat, Testimonial, TeamMember, VolunteerOpportunity,
                GalleryItem, Cause, CauseCategory, Centre,
                Post, Tag, Category, Author, Event, EventCategory,
            ]:
                model.objects.all().delete()

        self._seed_impact_stats()
        self._seed_events()
        self._seed_blog()
        self._seed_causes()
        self._seed_centres()
        self._seed_gallery()
        self._seed_volunteer_opportunities()
        self._seed_testimonials()
        self._seed_team_members()

        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))

    # ------------------------------------------------------------------
    # Impact Stats
    # ------------------------------------------------------------------
    def _seed_impact_stats(self):
        stats = [
            {'value': 38, 'suffix': '+ Years', 'label': 'of Spiritual Teaching', 'order': 1},
            {'value': 20000, 'suffix': '+', 'label': 'Lives Transformed', 'order': 2},
            {'value': 3, 'suffix': '+', 'label': 'Countries Reached', 'order': 3},
            {'value': 5, 'suffix': '+', 'label': 'Active Centres', 'order': 4},
        ]
        for s in stats:
            ImpactStat.objects.update_or_create(label=s['label'], defaults=s)
        self.stdout.write(f'  Created {len(stats)} impact stats')

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _seed_events(self):
        categories = {}
        for name in ['Spiritual Retreat', 'Meditation Workshop', 'Community Service']:
            obj, _ = EventCategory.objects.get_or_create(name=name)
            categories[name] = obj

        events_data = [
            {
                'slug': 'annual-spiritual-retreat-2026',
                'title': 'Annual Spiritual Retreat 2026',
                'description': 'A transformative five-day silent retreat immersing participants in deep meditation, conscious breathing, and contemplative teachings drawn from the Jan Cosmic Foundation tradition.',
                'content': '<p>Join us for the Jan Cosmic Foundation Annual Spiritual Retreat — a sacred gathering held in the serene hills of Aburi, Ghana. Over five days participants engage in extended silent sittings, guided breathwork sessions, and evening satsangs with Dr. Baffour Jan and senior facilitators.</p><p>Each morning begins with sunrise meditation on the open-air pavilion, followed by a mindful breakfast taken in noble silence. Afternoon sessions explore the philosophy of conscious living, non-attachment, and service as a spiritual path. Evening fires bring the community together for song, sharing, and celebration of the inner journey.</p><p>The retreat is suitable for both new and experienced meditators. Simple, nourishing vegetarian meals are included throughout the program. Accommodation is available on-site in shared or private rooms — limited spaces, early registration is encouraged.</p>',
                'date': date(2026, 4, 18),
                'end_date': date(2026, 4, 22),
                'time': time(8, 0),
                'location': 'Aburi Botanical Gardens Retreat Centre, Ghana',
                'address': 'Aburi Botanical Gardens, Eastern Region, Ghana',
                'category': categories['Spiritual Retreat'],
                'registration_url': '/events/annual-spiritual-retreat-2026/register',
                'is_published': True,
            },
            {
                'slug': 'meditation-intensive-accra-may-2026',
                'title': 'Meditation Intensive — Accra',
                'description': 'A weekend deep-dive into mindfulness and concentration meditation techniques for practitioners ready to expand their sitting practice.',
                'content': '<p>This two-day intensive is designed for meditators who already have a regular practice and want to deepen their understanding of concentration (samatha) and insight (vipassana) methods as taught within the JCF lineage.</p><p>Saturday covers the theory and neuroscience of contemplative practice, breath-based stabilisation techniques, and working skillfully with distraction. Sunday shifts to open awareness, noting practice, and practical strategies for sustaining depth in daily life.</p><p>The intensive is facilitated by Senior Teacher Abena Asante and includes guided sits, small-group inquiry, and one-on-one interviews. Participants should bring a meditation cushion or bench if they own one. Tea and light refreshments provided; lunch break is on your own.</p>',
                'date': date(2026, 5, 9),
                'end_date': date(2026, 5, 10),
                'time': time(9, 0),
                'location': 'JCF Accra Centre, Airport Residential Area',
                'address': 'Franko Estate, Kwabenya, Accra, Ghana',
                'category': categories['Meditation Workshop'],
                'registration_url': '/events/meditation-intensive-accra-may-2026/register',
                'is_published': True,
            },
            {
                'slug': 'community-clean-up-and-care-june-2026',
                'title': 'Community Clean-Up & Care Day',
                'description': 'Volunteers gather to beautify the Nima neighbourhood, distribute food packs, and visit the elderly — a day of hands-on service and joyful giving.',
                'content': '<p>Service is at the heart of the Jan Cosmic Foundation way of life. On this Community Clean-Up & Care Day, volunteers from all JCF centres across Ghana converge in Nima, Accra, to give back to one of the city\'s most vibrant and underserved communities.</p><p>Activities include a neighbourhood litter-collection walk, painting of public benches and murals, distribution of 500 care packages (food staples, soap, and sanitary items), and a visit to the Nima elderly care home where we share a meal and offer companionship.</p><p>The day closes with a shared communal lunch prepared by JCF volunteers, followed by a brief reflection circle. All ages and physical abilities are welcome — there is a task suited to everyone. Please register so we can prepare enough supplies.</p>',
                'date': date(2026, 6, 21),
                'time': time(7, 30),
                'location': 'Nima Community Centre, Accra',
                'address': 'Nima Road, Nima, Accra, Ghana',
                'category': categories['Community Service'],
                'registration_url': '/events/community-clean-up-and-care-june-2026/register',
                'is_published': True,
            },
            {
                'slug': 'winter-solstice-meditation-2025',
                'title': 'Winter Solstice Meditation Evening',
                'description': 'A special candlelit meditation and ceremony marking the winter solstice — a time of inner renewal and collective intention-setting for the year ahead.',
                'content': '<p>The JCF Kumasi Centre hosted a beautiful Winter Solstice Meditation Evening bringing together over 80 practitioners for three hours of silent meditation, chanting, and ceremony. Dr. Baffour Jan led the group in a guided journey through the darkness into light, using the symbolism of the solstice as a mirror for the inner path.</p><p>Participants set intentions for the coming year, released what no longer served them through a symbolic fire ceremony, and shared in a pot-luck feast celebrating the return of the light. The evening was a profound reminder of community, presence, and the cyclical nature of growth.</p>',
                'date': date(2025, 12, 21),
                'time': time(18, 0),
                'location': 'JCF Kumasi Centre',
                'address': '7 Nhyiaeso Road, Nhyiaeso, Kumasi, Ghana',
                'category': categories['Spiritual Retreat'],
                'is_published': True,
            },
            {
                'slug': 'youth-empowerment-workshop-september-2025',
                'title': 'Youth Empowerment Workshop',
                'description': 'A full-day workshop introducing young people aged 16–25 to conscious living, self-awareness, and purpose — through the lens of the JCF teachings.',
                'content': '<p>More than 120 young people from across Accra attended the JCF Youth Empowerment Workshop held at the Ghana Institute of Management and Public Administration. The programme blended awareness exercises, reflective inquiry, and practical sessions on discovering purpose and living with intention.</p><p>Sessions explored themes of self-knowledge, emotional awareness, and the difference between ambition driven by conditioning and action arising from genuine inner clarity. Participants left with a personal reflection journal, a community accountability partner, and free access to the JCF Youth Online Learning Hub for 12 months. The workshop was co-facilitated by JCF Youth Coordinator Kofi Mensah and Head of Community Partnerships Maame Agyapong.</p>',
                'date': date(2025, 9, 13),
                'time': time(9, 0),
                'location': 'GIMPA Conference Centre, Accra',
                'address': 'Greenhill, Achimota, Accra, Ghana',
                'category': categories['Community Service'],
                'is_published': True,
            },
            {
                'slug': 'mindfulness-in-healthcare-symposium-2025',
                'title': 'Mindfulness in Healthcare Symposium',
                'description': 'Clinicians, researchers, and practitioners gathered to explore evidence-based applications of contemplative practices in Ghanaian healthcare settings.',
                'content': '<p>The JCF partnered with the Ghana Health Service and the University of Ghana Medical School to host this one-day symposium at the Korle Bu Teaching Hospital Conference Hall. The event brought together 60 healthcare professionals, researchers, and meditation teachers to share findings and experiences at the intersection of contemplative practice and clinical care.</p><p>Keynote presentations covered mindfulness-based stress reduction (MBSR) outcomes in Ghanaian hospital settings, the integration of traditional healing wisdom with evidence-based practice, and practical implementation strategies for busy clinicians. The afternoon featured live demonstrations of bedside mindfulness protocols and group discussion panels.</p>',
                'date': date(2025, 6, 7),
                'time': time(8, 30),
                'location': 'Korle Bu Teaching Hospital, Accra',
                'address': 'Guggisberg Avenue, Korle Bu, Accra, Ghana',
                'category': categories['Meditation Workshop'],
                'is_published': True,
            },
        ]

        for data in events_data:
            Event.objects.update_or_create(slug=data['slug'], defaults=data)
        self.stdout.write(f'  Created {len(events_data)} events')

    # ------------------------------------------------------------------
    # Blog
    # ------------------------------------------------------------------
    def _seed_blog(self):
        # Authors
        authors = {}
        for a in [
            {'name': 'Dr. Baffour Jan', 'role': 'Founder & Spiritual Director'},
            {'name': 'Abena Asante', 'role': 'Senior Teacher & Programme Director'},
            {'name': 'Kofi Mensah', 'role': 'Youth Coordinator & Meditation Teacher'},
        ]:
            obj, _ = Author.objects.update_or_create(name=a['name'], defaults=a)
            authors[a['name']] = obj

        # Categories
        cats = {}
        for name in ['Spiritual Growth', 'Community Service', 'Meditation']:
            obj, _ = Category.objects.get_or_create(name=name)
            cats[name] = obj

        # Tags
        all_tags = [
            'meditation', 'stillness', 'mindfulness', 'inner peace', 'service',
            'giving', 'community', 'spiritual growth', 'ubuntu', 'habit',
            'daily practice', 'beginners', 'group meditation',
            'collective consciousness', 'retreat', 'science', 'children',
            'mentorship', 'consciousness', 'youth', 'Guide the Children',
            'gratitude', 'wellbeing', 'positive psychology', 'neuroscience',
        ]
        tag_objs = {}
        for t in all_tags:
            obj, _ = Tag.objects.get_or_create(name=t)
            tag_objs[t] = obj

        posts_data = [
            {
                'slug': 'the-art-of-inner-stillness',
                'title': 'The Art of Inner Stillness: Finding Peace in a Noisy World',
                'excerpt': 'In an age of relentless stimulation, the capacity to be genuinely still has become one of the rarest and most valuable of human gifts. Here is how to begin cultivating it.',
                'content': '<p>We live in a world that celebrates busyness. To be perpetually occupied is worn as a badge of importance. Yet beneath the noise, every human heart longs for the same thing: genuine peace.</p><p>The Jan Cosmic Foundation tradition teaches that stillness is not the absence of activity — it is the ground from which all truly purposeful action arises. The Ghanaian proverb reminds us: <em>"The river that makes the most noise has the least water."</em> Depth comes from learning to turn inward.</p><h3>Begin with the breath</h3><p>The simplest and most universally available gateway to inner stillness is the breath. Not controlling it, not manipulating it — simply noticing it. Three conscious breaths taken before a meeting, before a meal, before a difficult conversation can shift the entire quality of that experience.</p><h3>Create a daily anchor</h3><p>A brief dedicated period of silence each day — even 10 minutes — trains the nervous system to recognise stillness as a resource rather than a threat. Many of our centre members report that this single practice changed their relationship with stress more than anything else they had tried.</p><h3>Let stillness be useful, not merely restful</h3><p>True stillness is not passive. It is the condition in which wisdom surfaces, in which we hear the quiet voice that knows what truly matters. Silence is not empty — it is full of the answers we have not yet learned to listen for.</p><p>We invite you to explore this dimension of your life with us. Our upcoming meditation sessions and retreats offer a structured, community-held space for this exploration.</p>',
                'author': authors['Dr. Baffour Jan'],
                'category': cats['Spiritual Growth'],
                'status': 'published',
                'published_date': timezone.make_aware(datetime(2026, 2, 14, 10, 0)),
                'tags': ['meditation', 'stillness', 'mindfulness', 'inner peace'],
            },
            {
                'slug': 'service-as-a-spiritual-path',
                'title': 'Service as a Spiritual Path: Why Giving is the Greatest Practice',
                'excerpt': 'Many people seek spiritual growth through inward practice alone. But the great traditions all agree — genuine awakening is inseparable from genuine service.',
                'content': '<p>There is a common misunderstanding in spiritual circles that awakening is a private achievement — something attained in solitary caves, silent retreats, or years of inner work conducted in isolation from the world. The Jan Cosmic Foundation tradition respectfully challenges this view.</p><p>In our teaching, inner realisation and outer service are two wings of the same bird. The bird cannot fly with only one wing.</p><h3>Service dissolves the self</h3><p>When we genuinely serve another person — not to be seen, not to feel virtuous, but simply because they need help and we are able to give it — something remarkable happens: the ego, for a moment, steps aside. That stepping aside is precisely what meditation is training us to achieve. Service is meditation with your hands open.</p><h3>The Ghanaian Ubuntu principle</h3><p>The West African philosophical concept of <em>Ubuntu</em> — "I am because we are" — expresses this beautifully. Individual flourishing is not separate from collective flourishing. When we invest in our communities, we invest in ourselves at the deepest level.</p><h3>Starting small is still starting</h3><p>Service does not require grand gestures. A phone call to a lonely neighbour. Mentoring a young person in your field. Showing up consistently to a community project. The JCF\'s Community Service Days are designed precisely to make this step easy and joyful.</p><p>We invite you to join us at our next Community Care Day and discover for yourself why so many of our volunteers describe their service hours as the most spiritually alive moments of their week.</p>',
                'author': authors['Abena Asante'],
                'category': cats['Community Service'],
                'status': 'published',
                'published_date': timezone.make_aware(datetime(2026, 1, 28, 10, 0)),
                'tags': ['service', 'giving', 'community', 'spiritual growth', 'ubuntu'],
            },
            {
                'slug': 'building-a-daily-meditation-habit',
                'title': 'Building a Daily Meditation Habit That Actually Lasts',
                'excerpt': 'Most people who try meditation give up within a month. Here are the evidence-backed strategies our teachers have refined over decades to help practitioners build a sustainable practice.',
                'content': '<p>Beginning a meditation practice is easy. Sustaining one through the inevitable rough patches — the restless mornings, the busy seasons, the feeling that "nothing is happening" — is where most practitioners struggle.</p><p>Over 38 years of teaching meditation, the Jan Cosmic Foundation has worked with thousands of practitioners at every stage of the journey. Here is what we have learned about building a practice that lasts.</p><h3>1. Start embarrassingly small</h3><p>Five minutes is enough to start. Not 20 minutes. Not the 45-minute sessions you read about online. Five genuine, intentional minutes every single day will build the neural pathway of "I am someone who meditates" far more effectively than sporadic long sessions.</p><h3>2. Attach it to an existing anchor</h3><p>Habit science is clear: new behaviours stick best when attached to existing routines. Meditate immediately after your morning tea, immediately before your evening shower. Let the existing habit carry the new one.</p><h3>3. Lower the bar for what counts</h3><p>Many practitioners quit because they feel they are "doing it wrong" when thoughts arise. Thoughts arising is not failure — it is the practice. Every time you notice a thought and return to the breath, that is one repetition of the mental muscle you are building. A session full of thoughts and full of returns is an excellent session.</p><h3>4. Find community</h3><p>This is perhaps the single most underrated factor. Practitioners who meditate within a community — even via a weekly group session — maintain their practice at dramatically higher rates than solo practitioners. Our centres hold weekly group sits open to all. Come once. Feel the difference.</p>',
                'author': authors['Kofi Mensah'],
                'category': cats['Meditation'],
                'status': 'published',
                'published_date': timezone.make_aware(datetime(2026, 1, 10, 10, 0)),
                'tags': ['meditation', 'habit', 'daily practice', 'beginners', 'mindfulness'],
            },
            {
                'slug': 'the-power-of-collective-intention',
                'title': 'The Power of Collective Intention: What Science and Spirit Agree On',
                'excerpt': 'Research on group meditation, the science of coherence, and ancient wisdom all point to the same surprising conclusion: consciousness shared is consciousness amplified.',
                'content': '<p>When we sit in meditation alone, we draw from our own reservoir. When we sit together, something qualitatively different becomes available. This is not mysticism — it is increasingly supported by rigorous research.</p><p>Studies from the HeartMath Institute and Maharishi University have documented measurable shifts in environmental stress indicators — crime rates, hospital admissions, accident rates — correlated with large groups meditating together in a given area. The mechanism is debated; the data is not.</p><h3>What our retreat participants consistently report</h3><p>At every Annual Spiritual Retreat, we survey participants before, during, and after the experience. Year after year, the finding is the same: even practitioners who have meditated alone for years describe the group silence as deeper, more effortless, and more nourishing than anything they regularly access in solo practice.</p><h3>The neuroscience of social resonance</h3><p>Human nervous systems are designed to co-regulate. Mirror neurons, the vagal tone system, and breathing entrainment are all mechanisms by which bodies in proximity influence one another\'s physiological states. A calm, coherent group pulls individuals toward greater calm and coherence. This is biology as much as spirituality.</p><h3>Creating your own collective</h3><p>You do not need a large retreat to access this. Inviting two or three friends to sit together once a week creates a meaningful field of collective intention. Begin simply: agree on a time, sit for 20 minutes together, and close with a brief sharing. The JCF centres are also always open for community sits — check our events page for scheduled group meditation sessions near you.</p>',
                'author': authors['Dr. Baffour Jan'],
                'category': cats['Spiritual Growth'],
                'status': 'published',
                'published_date': timezone.make_aware(datetime(2025, 12, 5, 10, 0)),
                'tags': ['group meditation', 'collective consciousness', 'retreat', 'science', 'community'],
            },
            {
                'slug': 'guide-the-children-shaping-young-minds',
                'title': 'How the Guide the Children Initiative is Shaping Young Minds',
                'excerpt': 'Through mentorship, awareness practices, and wisdom-based education, the Guide the Children programme is planting seeds of consciousness in the next generation.',
                'content': '<p>Children are naturally open. They have not yet built the layers of conditioning that make inner work so effortful for adults. The Guide the Children initiative was created by the Jan Cosmic Foundation to meet children in that openness — and nurture it before the world teaches them to close it off.</p><h3>More than academics</h3><p>Guide the Children is not a tutoring programme. It is an introduction to conscious living. Through age-appropriate awareness exercises, storytelling drawn from wisdom traditions, and creative expression, children learn to notice their thoughts, name their emotions, and relate to others with presence and compassion.</p><h3>What we are seeing</h3><p>Facilitators report that children who participate over multiple programme cycles show a visible shift in how they handle conflict, how they listen, and how they speak about themselves. Parents consistently tell us their children are calmer, more reflective, and more willing to help at home.</p><h3>The role of mentors</h3><p>Each child in the programme is paired with a volunteer mentor — not to instruct, but to be present. Mentors model attentiveness, curiosity, and stillness. In the JCF tradition, we believe that consciousness is caught more than it is taught, and the mentor relationship is where that transmission happens most naturally.</p><p>If you feel drawn to support this work — whether through volunteering as a mentor, donating educational materials, or simply spreading the word — visit the Guide the Children cause page to learn more.</p>',
                'author': authors['Abena Asante'],
                'category': cats['Community Service'],
                'status': 'published',
                'published_date': timezone.make_aware(datetime(2025, 11, 18, 10, 0)),
                'tags': ['children', 'mentorship', 'consciousness', 'youth', 'Guide the Children'],
            },
            {
                'slug': 'gratitude-practice-a-scientific-and-spiritual-perspective',
                'title': 'Gratitude Practice: A Scientific and Spiritual Perspective',
                'excerpt': 'Gratitude is one of the most extensively researched wellbeing practices in positive psychology — and one of the most celebrated in contemplative traditions. Here is why it works and how to do it effectively.',
                'content': '<p>If you had to choose a single daily practice for wellbeing, the evidence would point strongly to gratitude. Dozens of randomised controlled trials have documented its effects on depression, anxiety, sleep quality, immune function, and social connection. Contemplative traditions have recommended it for millennia. The convergence is striking.</p><h3>Why gratitude works neurologically</h3><p>The brain\'s default mode — absent other instructions — tends toward what psychologists call the negativity bias: scanning for threats, rehearsing grievances, anticipating problems. This served our ancestors well on the savannah. It serves us less well in modern life. Gratitude practice deliberately trains the brain to also scan for what is working, what is beautiful, what has been given. Over time, this rebalances the default mode.</p><h3>The spiritual dimension</h3><p>In the JCF tradition, gratitude is more than a psychological technique. It is an orientation toward life itself — a recognition that existence is gift, that consciousness is gift, that community is gift. Practiced at this depth, gratitude naturally opens into what the great traditions call devotion or bhakti: the heart moved by beauty into service.</p><h3>A simple gratitude practice</h3><p>Each evening, write three specific things you are grateful for — not general things ("my health") but specific things ("the conversation with my colleague this afternoon that helped me see the problem differently"). Specificity is what produces the neurological benefit. After 21 days, notice what has shifted.</p><p>We invite you to share your experience with our community. The JCF online forum — accessible to all centre members — has an active gratitude thread where hundreds of practitioners have been posting daily for over two years.</p>',
                'author': authors['Kofi Mensah'],
                'category': cats['Meditation'],
                'status': 'published',
                'published_date': timezone.make_aware(datetime(2025, 10, 22, 10, 0)),
                'tags': ['gratitude', 'wellbeing', 'positive psychology', 'daily practice', 'neuroscience'],
            },
        ]

        for data in posts_data:
            tag_names = data.pop('tags')
            post, _ = Post.objects.update_or_create(slug=data['slug'], defaults=data)
            post.tags.set([tag_objs[t] for t in tag_names])
        self.stdout.write(f'  Created {len(posts_data)} blog posts')

    # ------------------------------------------------------------------
    # Causes + seed donations for raised amounts
    # ------------------------------------------------------------------
    def _seed_causes(self):
        cats = {}
        for name in ['Infrastructure', 'Sustainability', 'Media', 'Youth Development']:
            obj, _ = CauseCategory.objects.get_or_create(name=name)
            cats[name] = obj

        causes_data = [
            {
                'slug': 'kwahu-land-project',
                'title': 'JCF Kwahu Land Project',
                'description': 'Acquiring a 500-acre parcel of land in Kwahu, Eastern Region of Ghana, to establish a JCF Spiritual Village with retreat facilities, organic farms, and spaces for meditation and community living.',
                'content': '<p>One of the primary initiatives of the Jan Cosmic Foundation is the acquisition of a 500-acre parcel of land in Kwahu, in the Eastern Region of Ghana. This land is envisioned as the foundation for a long-term spiritual and ecological project.</p><p>The project includes the development of organic farming and sustainable agriculture, a JCF Spiritual Village, a retreat centre for spiritual seekers, and dedicated spaces for meditation, learning, and community living.</p><p>The JCF Village is intended to function as a sanctuary for individuals seeking deeper spiritual understanding, similar in spirit to global spiritual retreat centres. Visitors will be able to stay for retreats, programmes, and periods of personal spiritual practice.</p><p>Your donations toward this project support land acquisition, infrastructure development, environmental restoration, and the construction of facilities for retreats and spiritual programmes.</p>',
                'goal_amount': Decimal('500000.00'),
                'category': cats['Infrastructure'],
                'raised_seed': Decimal('60000.00'),
                'donors_seed': 4,
            },
            {
                'slug': 'organic-farming-initiative',
                'title': 'JCF Organic Farming Initiative',
                'description': 'Supporting sustainable organic farming on the Kwahu land — producing healthy, chemical-free food while demonstrating conscious living in harmony with nature.',
                'content': '<p>Alongside the Kwahu Land Project, organic farming activities have already begun on portions of the land, even though the full acquisition is still in progress.</p><p>The organic farms serve several purposes: producing healthy, chemical-free food, demonstrating sustainable agricultural practices, supporting the future JCF village community, and creating a model for conscious living in harmony with nature.</p><p>This initiative reflects the foundation\'s belief that spiritual growth and care for the earth are inseparable. By cultivating the land with respect and awareness, we practise the same principles we teach — aligning human life with universal intelligence.</p><p>Donations toward this initiative help support farming equipment, irrigation systems, seeds and organic inputs, and farm infrastructure and operations.</p>',
                'goal_amount': Decimal('80000.00'),
                'category': cats['Sustainability'],
                'raised_seed': Decimal('34000.00'),
                'donors_seed': 145,
            },
            {
                'slug': 'media-digital-outreach',
                'title': 'JCF Media & Digital Outreach',
                'description': 'Ensuring the teachings and work of Dr. Baffour Jan reach a wider audience through professional media production, digital platforms, and modern technology.',
                'content': '<p>The JCF Media Team plays a critical role in spreading the teachings and work of Dr. Baffour Jan and the Jan Cosmic Foundation to seekers everywhere.</p><p>The media team is responsible for recording and producing teachings and talks, editing and publishing video content, managing digital platforms and websites, producing written content and publications, and maintaining the foundation\'s IT systems and online presence.</p><p>This work ensures that spiritual teachings and insights reach a wider audience through modern media and technology. As Dr. Baffour Jan teaches, "The entire cosmos becomes accessible if we learn to speak the cosmic language" — and digital media is one of the ways we speak that language today.</p><p>Donations support video and audio production equipment, editing and media software, content production, website and digital infrastructure, and media team operations.</p>',
                'goal_amount': Decimal('60000.00'),
                'category': cats['Media'],
                'raised_seed': Decimal('2000.00'),
                'donors_seed': 2,
            },
            {
                'slug': 'guide-the-children',
                'title': 'Guide the Children Initiative',
                'description': 'Introducing children to a more conscious way of living through educational activities, mentorship, and learning approaches that plant seeds of wisdom and awareness early in life.',
                'content': '<p>The Guide the Children initiative is a programme created by the Jan Cosmic Foundation to introduce children to a more conscious way of living and thinking.</p><p>The programme aims to help young people develop awareness and emotional intelligence, understand deeper aspects of life and existence, cultivate compassion, responsibility, and clarity, and grow beyond limiting social conditioning.</p><p>Through educational activities, mentorship, and conscious learning approaches, the initiative seeks to plant seeds of wisdom and awareness early in life. As Dr. Baffour Jan teaches, every human being carries within them the potential to awaken to higher states of consciousness — and nurturing this potential in children is among the most meaningful work we can do.</p><p>Donations help support educational materials, children\'s programmes and workshops, outreach activities, and the development of learning resources.</p>',
                'goal_amount': Decimal('45000.00'),
                'category': cats['Youth Development'],
                'raised_seed': Decimal('0.00'),
                'donors_seed': 0,
            },
            {
                'slug': 'community-centre-kumasi',
                'title': 'Kumasi Community Centre Expansion',
                'description': 'Expanding the JCF Kumasi Community Centre to serve the growing spiritual community — adding meditation halls, learning spaces, and facilities for retreats and programmes.',
                'content': '<p>The JCF Kumasi Community Centre has been a vital resource for the local spiritual community since its opening. Over the years, demand for its programmes — meditation sessions, spiritual teachings, retreats, and community gatherings — has grown to the point that the existing facility is consistently at capacity.</p><p>This expansion campaign will fund the construction of additional meditation and teaching spaces, a library, and a multi-purpose hall for community events, large gatherings, and training workshops.</p><p>The expanded centre will enable the JCF to welcome more seekers into the community and provide a permanent home for programmes that currently operate from rented spaces.</p><p>With your support, the expanded centre will become a beacon of spiritual growth and community service in the Ashanti Region.</p>',
                'goal_amount': Decimal('60000.00'),
                'category': cats['Infrastructure'],
                'raised_seed': Decimal('3500.00'),
                'donors_seed': 187,
            },
        ]

        for data in causes_data:
            raised = data.pop('raised_seed')
            donors = data.pop('donors_seed')
            cause, created = Cause.objects.update_or_create(slug=data['slug'], defaults=data)

            # Create seed donations to match the mock raised amounts
            if created and raised > 0 and donors > 0:
                per_donor = raised / donors
                for i in range(donors):
                    Donation.objects.create(
                        cause=cause,
                        donor_name=f'Seed Donor {i + 1}',
                        donor_email=f'donor{i + 1}@seed.example',
                        amount=per_donor,
                        currency='GHS',
                        method='online',
                        status='completed',
                        donated_at=timezone.now(),
                    )

        self.stdout.write(f'  Created {len(causes_data)} causes with seed donations')

    # ------------------------------------------------------------------
    # Centres
    # ------------------------------------------------------------------
    def _seed_centres(self):
        centres_data = [
            {
                'slug': 'accra-ghana',
                'name': 'JCF Accra Centre',
                'location': 'Accra, Ghana',
                'address': 'Franko Estate, Kwabenya, Accra, Ghana',
                'country': 'Ghana',
                'description': 'The founding and flagship centre of the Jan Cosmic Foundation, established in 1988. The Accra Centre hosts the largest meditation community in West Africa, offering daily sits, weekly satsangs, teacher training, and a full calendar of community service programmes. It is home to the JCF Secretariat and the primary coordination hub for all centre activities.',
                'member_count': 620,
                'leader_name': 'Dr. Baffour Jan',
                'leader_title': 'Founder & Spiritual Director',
                'contact_email': 'info@jancosmicfoundation.org',
                'contact_phone': '+233550590054',
                'latitude': Decimal('5.6037'),
                'longitude': Decimal('-0.1870'),
            },
            {
                'slug': 'kumasi-ghana',
                'name': 'JCF Kumasi Centre',
                'location': 'Kumasi, Ghana',
                'address': '7 Nhyiaeso Road, Nhyiaeso, Kumasi, Ashanti Region, Ghana',
                'country': 'Ghana',
                'description': 'The Kumasi Centre serves the Ashanti Region and surrounding areas with a strong focus on community service and youth programmes. It operates the JCF Community Centre in Nhyiaeso — a hub for free tutoring, vocational training, and weekly health clinics — and hosts the JCF Youth Empowerment Programme cohort for the region.',
                'member_count': 310,
                'leader_name': 'Yaw Boateng',
                'leader_title': 'Centre Director',
                'contact_email': 'kumasi@jancosmicfoundation.org',
                'contact_phone': '+233322021870',
                'latitude': Decimal('6.6885'),
                'longitude': Decimal('-1.6244'),
            },
            {
                'slug': 'london-uk',
                'name': 'JCF London Centre',
                'location': 'London, United Kingdom',
                'address': '42 Coldharbour Lane, Brixton, London, SE5 9NR, United Kingdom',
                'country': 'United Kingdom',
                'description': 'The JCF London Centre was established in 2001 to serve the significant Ghanaian diaspora community in the UK and has grown into a multicultural spiritual and service community. Weekly meditation sessions, monthly community gatherings, and annual fundraising events for Ghana-based programmes are the pillars of London Centre life. The centre also coordinates JCF UK volunteer travel programmes to Ghana.',
                'member_count': 185,
                'leader_name': 'Adwoa Boakye-Mensah',
                'leader_title': 'Centre Director',
                'contact_email': 'london@jancosmicfoundation.org',
                'contact_phone': '+442077374290',
                'latitude': Decimal('51.4611'),
                'longitude': Decimal('-0.0999'),
            },
            {
                'slug': 'new-york-usa',
                'name': 'JCF New York Centre',
                'location': 'New York, USA',
                'address': '235 West 116th Street, Harlem, New York, NY 10026, USA',
                'country': 'United States of America',
                'description': 'Located in the heart of Harlem, the JCF New York Centre brings together the Ghanaian diaspora alongside a broader community of practitioners drawn to the JCF tradition. The centre is particularly active in the local African immigrant support community, partnering with neighbourhood organisations for housing assistance, legal aid clinics, and cultural events celebrating the African heritage.',
                'member_count': 140,
                'leader_name': 'Kwame Ofori-Atta',
                'leader_title': 'Centre Director',
                'contact_email': 'newyork@jancosmicfoundation.org',
                'contact_phone': '+12128665540',
                'latitude': Decimal('40.8008'),
                'longitude': Decimal('-73.9535'),
            },
            {
                'slug': 'toronto-canada',
                'name': 'JCF Toronto Centre',
                'location': 'Toronto, Canada',
                'address': '1180 Finch Avenue West, North York, Toronto, ON M3J 2E4, Canada',
                'country': 'Canada',
                'description': 'The JCF Toronto Centre was established in 2009 and has become one of the most active diaspora centres outside Ghana. It hosts the largest annual JCF fundraising gala in North America, raising significant funds each year for the Ghana-based scholarship and medical outreach programmes. The centre also runs a popular monthly cultural and spiritual evening open to the broader Toronto community.',
                'member_count': 165,
                'leader_name': 'Ama Sarpong',
                'leader_title': 'Centre Director',
                'contact_email': 'toronto@jancosmicfoundation.org',
                'contact_phone': '+14167392211',
                'latitude': Decimal('43.7615'),
                'longitude': Decimal('-79.4875'),
            },
        ]

        for data in centres_data:
            Centre.objects.update_or_create(slug=data['slug'], defaults=data)
        self.stdout.write(f'  Created {len(centres_data)} centres')

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _seed_gallery(self):
        items = [
            {'title': 'Annual Spiritual Retreat — Group Meditation', 'description': 'Over 200 practitioners in silent group meditation at the Aburi Retreat Centre during the 2025 Annual Spiritual Retreat.', 'type': 'image', 'category': 'events', 'date': date(2025, 4, 20)},
            {'title': 'Youth Empowerment Workshop — Accra 2025', 'description': 'Young participants at the September 2025 Youth Empowerment Workshop engaging in a goal-setting exercise at GIMPA.', 'type': 'image', 'category': 'events', 'date': date(2025, 9, 13)},
            {'title': 'Winter Solstice Fire Ceremony', 'description': 'Community members gathered around the ceremonial fire at the Kumasi Centre during the 2025 Winter Solstice evening.', 'type': 'image', 'category': 'events', 'date': date(2025, 12, 21)},
            {'title': 'Nima Community Clean-Up 2025', 'description': 'JCF volunteers clearing litter and painting murals along Nima Road during the May 2025 Community Care Day.', 'type': 'image', 'category': 'community', 'date': date(2025, 5, 17)},
            {'title': 'Medical Outreach — Upper East Region', 'description': 'JCF medical team conducting free health screenings in Bawku during the Northern Ghana Medical Outreach programme.', 'type': 'image', 'category': 'community', 'date': date(2025, 8, 9)},
            {'title': 'Scholarship Presentation Ceremony', 'description': 'Dr. Baffour Jan presenting scholarship certificates to the 2025 cohort of JCF Education Scholarship recipients.', 'type': 'image', 'category': 'community', 'date': date(2025, 7, 5)},
            {'title': 'Morning Meditation — Aburi Retreat', 'description': 'Sunrise meditation session on the open-air pavilion overlooking the Aburi hills. A cherished daily ritual of the annual retreat.', 'type': 'image', 'category': 'spiritual', 'date': date(2025, 4, 19)},
            {'title': 'Satsang with Dr. Baffour Jan', 'description': 'An intimate evening satsang with the Founder during the 2025 Annual Retreat — a question and answer gathering held under the stars.', 'type': 'image', 'category': 'spiritual', 'date': date(2025, 4, 21)},
            {'title': 'Mindfulness in Healthcare Symposium', 'description': 'Clinicians and meditation teachers in discussion at the Korle Bu Teaching Hospital symposium, June 2025.', 'type': 'image', 'category': 'spiritual', 'date': date(2025, 6, 7)},
            {'title': 'JCF Accra Centre — Main Hall', 'description': 'The beautifully appointed main meditation hall of the JCF Accra Centre, which seats up to 150 practitioners.', 'type': 'image', 'category': 'centres', 'date': date(2025, 3, 15)},
            {'title': 'JCF London Centre — Community Gathering', 'description': 'Members of the JCF London Centre at their annual summer community gathering in Brockwell Park, Brixton.', 'type': 'image', 'category': 'centres', 'date': date(2025, 7, 27)},
            {'title': 'JCF Toronto Annual Gala', 'description': 'The 2025 JCF Toronto Fundraising Gala — an evening of music, food, and celebration that raised GHS 85,000 for Ghana-based programmes.', 'type': 'image', 'category': 'centres', 'date': date(2025, 11, 8)},
        ]

        for item in items:
            GalleryItem.objects.update_or_create(title=item['title'], defaults=item)
        self.stdout.write(f'  Created {len(items)} gallery items')

    # ------------------------------------------------------------------
    # Volunteer Opportunities
    # ------------------------------------------------------------------
    def _seed_volunteer_opportunities(self):
        opps = [
            {
                'title': 'Community Outreach Coordinator',
                'description': 'Coordinate and participate in our regular community service days — organising logistics, liaising with partner organisations, and ensuring volunteers have a meaningful and well-supported experience in the field.',
                'location': 'Accra or Kumasi, Ghana',
                'commitment': '1 day per month minimum, plus occasional weeknight planning meetings',
                'skills': ['Organisation', 'Communication', 'Community relations', 'Problem solving'],
            },
            {
                'title': 'Meditation Session Facilitator',
                'description': 'Lead or co-facilitate weekly community meditation sessions at your local JCF centre or an outreach location. Training and ongoing mentorship are provided by senior JCF teachers. An existing personal practice is required; formal teaching credentials are not.',
                'location': 'Any JCF Centre (Accra, Kumasi, London, New York, Toronto)',
                'commitment': '2–4 hours per week',
                'skills': ['Personal meditation practice', 'Public speaking', 'Empathy', 'Reliability'],
            },
            {
                'title': 'Youth Mentor',
                'description': "Provide presence-based mentorship to young people in the Guide the Children initiative and the Youth Empowerment Programme. Mentors commit to regular meetings with their mentees over a 12-week programme cycle, offering attentive listening, encouragement, and the kind of grounded support that comes from being genuinely present.",
                'location': 'Flexible — in-person or online',
                'commitment': '2 hours per week for 12 weeks per programme cycle',
                'skills': ['Professional experience in any field', 'Active listening', 'Patience', 'Commitment'],
            },
            {
                'title': 'Digital & Communications Volunteer',
                'description': 'Support the JCF communications team with social media content, website updates, photography and videography at events, newsletter production, and graphic design. This role is ideal for creative professionals who want to contribute their skills to a cause they believe in.',
                'location': 'Remote, with occasional in-person events in Accra',
                'commitment': 'Flexible — approximately 4–6 hours per month',
                'skills': ['Social media', 'Photography / Videography', 'Graphic design', 'Writing', 'WordPress or web skills'],
            },
        ]

        for opp in opps:
            VolunteerOpportunity.objects.update_or_create(title=opp['title'], defaults=opp)
        self.stdout.write(f'  Created {len(opps)} volunteer opportunities')

    # ------------------------------------------------------------------
    # Testimonials
    # ------------------------------------------------------------------
    def _seed_testimonials(self):
        testimonials = [
            {
                'name': 'Esi Amponsah',
                'role': 'Seeker & Volunteer — Accra Centre',
                'quote': 'Before I found JCF, I was successful on the outside but completely lost on the inside. The teachings of Dr. Jan helped me see that the restlessness I felt was not a problem to solve — it was a call to wake up. The community of seekers here has become my spiritual family.',
                'order': 1,
            },
            {
                'name': 'James Osei-Bonsu',
                'role': 'Meditation Facilitator — Kumasi Centre',
                'quote': 'What drew me to JCF was the directness. No dogma, no rituals for the sake of rituals — just a clear invitation to know yourself at the deepest level. Facilitating meditation sessions has become my way of giving back what was so generously given to me: the possibility of inner freedom.',
                'order': 2,
            },
            {
                'name': 'Nana Akua Twum',
                'role': 'Guide the Children Mentor — Accra',
                'quote': 'Mentoring children in the Guide the Children programme has taught me that consciousness is not something you lecture about — it is something you transmit through presence. When I sit with these young ones, I see them soften, open up, and begin to ask the questions that matter. It transforms me as much as it transforms them.',
                'order': 3,
            },
            {
                'name': 'David Asiedu-Antwi',
                'role': 'Member — London Centre',
                'quote': 'Living in London, far from Ghana, I thought the spiritual path was something I would have to walk alone. The JCF London Centre proved me wrong. The weekly group sits, the satsangs, and the community of seekers have shown me that self-realization is not a solitary pursuit — it deepens in the company of others who are also reaching for the truth.',
                'order': 4,
            },
        ]

        for t in testimonials:
            Testimonial.objects.update_or_create(name=t['name'], defaults=t)
        self.stdout.write(f'  Created {len(testimonials)} testimonials')

    # ------------------------------------------------------------------
    # Team Members
    # ------------------------------------------------------------------
    def _seed_team_members(self):
        members = [
            {
                'name': 'Dr. Baffour Jan',
                'role': 'Founder & Spiritual Director',
                'bio': "Dr. Baffour Jan is a spiritual master, mystic, and teacher who founded the Jan Cosmic Foundation in Accra in 1988. For over 38 years he has guided seekers toward self-realization, teaching that the evolution of consciousness and selfless service are inseparable dimensions of the same path. Under his guidance, the JCF has grown from a small meditation circle in Airport Residential Area to an international community spanning five countries and touching over 20,000 lives. He is the author of three books on consciousness and higher living, a deeply sought-after retreat teacher, and above all, a living example of the inner freedom he points others toward.",
                'order': 1,
            },
            {
                'name': 'Abena Asante',
                'role': 'Senior Teacher & Programme Director',
                'bio': "Abena Asante has been a core member of the JCF community since 2003 and a certified meditation teacher within the JCF lineage since 2009. As Programme Director, she oversees the development and delivery of all JCF training and educational offerings, including the Teacher Training Programme, the Youth Empowerment curriculum, and the annual retreat calendar. Grounded in the teachings of Dr. Baffour Jan, she is passionate about making contemplative practice accessible across cultural and economic lines. She leads the Women's Wisdom Circle at the Accra Centre and is a regular contributor to the JCF blog.",
                'order': 2,
            },
            {
                'name': 'Kofi Mensah',
                'role': 'Youth Coordinator & Meditation Teacher',
                'bio': "Kofi Mensah was a young seeker drawn to Dr. Jan's teachings in 2012, and that encounter set the course of his life. He returned to the JCF as a staff member in 2018, bringing the same fire that first brought him through the door. As Youth Coordinator, he leads the Youth Empowerment Programme, manages the mentorship network, and serves as the primary point of contact for young people engaging with the JCF for the first time. A certified meditation teacher, Kofi brings warmth, energy, and lived experience to his work with young people. He co-authored the JCF Youth Mindfulness Curriculum and frequently speaks at schools and universities across Ghana.",
                'order': 3,
            },
            {
                'name': 'Maame Agyapong',
                'role': 'Head of Community Partnerships & Outreach',
                'bio': "Maame Agyapong leads the JCF's relationships with partner organisations, government agencies, and community institutions. With a background in public health and community development, she oversees the Guide the Children outreach activities, the Community Service Days calendar, and the JCF's growing portfolio of collaborative projects with institutions such as the Ghana Health Service and the University of Ghana. She serves on the boards of two Ghana-based charitable organisations. Her work ensures that the JCF's service programmes are rooted in genuine community need and delivered with the highest standards of care and accountability.",
                'order': 4,
            },
        ]

        for m in members:
            TeamMember.objects.update_or_create(name=m['name'], defaults=m)
        self.stdout.write(f'  Created {len(members)} team members')
