import os
import time
import logging
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

# Fallback curated imagery (pediatric, warm, professional)
FALLBACK_IMAGES = {
    'parenting': 'https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=800&q=80',
    'nutrition': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
    'safety': 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?auto=format&fit=crop&w=800&q=80',
    'fever': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
    'cough': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
    'colds': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
    'diarrhea': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
    'general': 'https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=800&q=80',
}

# Rich curated fallback articles if NewsAPI is offline or rate-limited
CURATED_FALLBACK_ARTICLES = {
    'parenting': [
        {
            'title': 'Positive Parenting: Building Emotional Resilience in Young Children',
            'description': 'Child psychologists share core techniques for validating toddlers’ emotions while setting calm, consistent developmental boundaries at home.',
            'source': 'American Academy of Pediatrics',
            'url': 'https://www.healthychildren.org/English/family-life/family-dynamics/communication-discipline/Pages/Positive-Discipline-and-Child-Guidance.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-12T08:00:00Z',
            'category': 'parenting',
        },
        {
            'title': 'The Power of Reading Aloud: Language Milestones for Ages 1 to 5',
            'description': 'How 15 minutes of daily interactive storytelling stimulates vocabulary expansion, cognitive development, and secure parental bonding.',
            'source': 'Zero to Three Early Learning',
            'url': 'https://www.zerotothree.org/resource/developing-early-literacy-skills/',
            'urlToImage': 'https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-10T11:30:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Managing Toddler Tantrums with Mindful Co-Regulation',
            'description': 'Evidence-backed strategies to help parents remain calm and provide soothing physical reassurance during intense sensory meltdowns.',
            'source': 'Child Mind Institute',
            'url': 'https://childmind.org/article/how-to-handle-tantrums-and-meltdowns/',
            'urlToImage': 'https://images.unsplash.com/photo-1476703993599-0035a21b17a9?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-08T14:15:00Z',
            'category': 'parenting',
        },
    ],
    'nutrition': [
        {
            'title': 'Iron and Brain Growth: Essential Nutrient Timing for Infants & Toddlers',
            'description': 'Why adequate dietary iron and zinc intake in early childhood are critical for cognitive milestones, and which whole foods provide optimal absorption.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/healthy-living/nutrition/Pages/Iron-Deficiency-Anemia.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-14T09:00:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Navigating Picky Eating: The "Division of Responsibility" Method',
            'description': 'Pediatric dietitians explain how parents decide what, when, and where food is served, allowing the child autonomy over how much to eat.',
            'source': 'Ellyn Satter Institute',
            'url': 'https://www.ellynsatterinstitute.org/how-to-feed/the-division-of-responsibility-in-feeding/',
            'urlToImage': 'https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-11T12:00:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Smart Finger Foods for Self-Feeding and Fine Motor Development',
            'description': 'Safe, nutrient-dense soft food finger options that encourage independent hand-to-mouth coordination without choking risks.',
            'source': 'Pediatric Nutrition Network',
            'url': 'https://www.eatright.org/food/nutrition/dietary-guidelines-and-myplate/finger-foods-for-babies',
            'urlToImage': 'https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-09T16:20:00Z',
            'category': 'nutrition',
        },
    ],
    'safety': [
        {
            'title': 'Complete Home Babyproofing Checklist by Developmental Stage',
            'description': 'From anchor straps on heavy furniture to outlet locks and stair gates, essential preventative measures for crawling and walking infants.',
            'source': 'Safe Kids Worldwide',
            'url': 'https://www.safekids.org/safetytips/field_risks/home-safety',
            'urlToImage': 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-13T10:00:00Z',
            'category': 'safety',
        },
        {
            'title': 'Safe Sleep Environments: Updated Pediatric Guidelines',
            'description': 'Key recommendations on firm mattresses, back-sleeping, eliminating loose blankets, and sharing a room without bed-sharing.',
            'source': 'AAP Pediatric Guidance',
            'url': 'https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/A-Parents-Guide-to-Safe-Sleep.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-07T15:00:00Z',
            'category': 'safety',
        },
        {
            'title': 'Water Safety at Home: Bath Time and Small Pool Precautions',
            'description': 'Why touch supervision is mandatory whenever young children are near standing water, and how to eliminate unexpected bathroom hazards.',
            'source': 'Mayo Clinic Health',
            'url': 'https://www.mayoclinic.org/healthy-lifestyle/infant-and-toddler-health/in-depth/child-safety/art-20044744',
            'urlToImage': 'https://images.unsplash.com/photo-1508873696983-2df5293cb32f?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-05T13:45:00Z',
            'category': 'safety',
        },
    ],
    'fever': [
        {
            'title': 'Managing Childhood Fevers: Comfort Measures vs. Medication Timing',
            'description': 'Pediatricians explain when fever is fighting infection, safe weight-based dosing for antipyretics, and key signs that warrant clinical evaluation.',
            'source': 'AAP HealthyChildren',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/fever/Pages/Fever-and-Your-Baby.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-14T07:30:00Z',
            'category': 'fever',
        },
        {
            'title': 'Hydration During Fevers: Preventing Fluid Loss in Toddlers',
            'description': 'Practical ways to offer small, frequent sips of electrolyte solutions and breastmilk to keep children hydrated while their temperature is elevated.',
            'source': 'Children’s Hospital Health',
            'url': 'https://www.seattlechildrens.org/conditions/a-z/fever/',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-12T11:00:00Z',
            'category': 'fever',
        },
    ],
    'cough': [
        {
            'title': 'Cough Care for Little Lungs: Cool Mist, Hydration & Honey Guidance',
            'description': 'Why over-the-counter cough syrups are discouraged for young kids, and how natural honey (for age 1+) and elevation provide gentle relief.',
            'source': 'American Academy of Pediatrics',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/chest-lungs/Pages/Coughs-and-Colds-Medicines-or-Home-Remedies.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-13T14:00:00Z',
            'category': 'cough',
        },
        {
            'title': 'Barking Cough or Stridor: Recognizing Croup in Young Children',
            'description': 'Learn the distinction between routine viral coughs and croup, plus how cool night air or bathroom steam can soothe sudden nocturnal episodes.',
            'source': 'Mayo Clinic Pediatrics',
            'url': 'https://www.mayoclinic.org/diseases-conditions/croup/symptoms-causes/syc-20350348',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-10T09:30:00Z',
            'category': 'cough',
        },
    ],
    'colds': [
        {
            'title': 'Clearing Stuffy Toddler Noses: Saline Sprays and Gentle Suction',
            'description': 'How to safely thin mucus with sterile saline drops before feeding and sleeping to improve breathing and promote restful recovery.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/ear-nose-throat/Pages/Children-and-Colds.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-14T10:00:00Z',
            'category': 'colds',
        },
        {
            'title': 'Understanding Viral Cold Duration: What Is Normal for Toddlers?',
            'description': 'Most common cold symptoms peak on days 3–5 and resolve in 10–14 days. Here is what pediatricians look for to rule out secondary ear infections.',
            'source': 'CDC Pediatric Health',
            'url': 'https://www.cdc.gov/antibiotic-use/common-cold.html',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-11T08:45:00Z',
            'category': 'colds',
        },
    ],
    'diarrhea': [
        {
            'title': 'Oral Rehydration Therapy: Keeping Toddlers Hydrated During Stomach Bugs',
            'description': 'How balanced oral electrolyte solution restores essential sodium and potassium safely during acute bouts of childhood gastroenteritis.',
            'source': 'World Health Organization (WHO)',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/abdominal/Pages/Diarrhea.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-13T16:00:00Z',
            'category': 'diarrhea',
        },
        {
            'title': 'Dietary Guidance for Tummy Recovery: Continuation of Normal Feeding',
            'description': 'Why modern pediatric medicine recommends returning promptly to age-appropriate nutritious foods rather than prolonged restrictive diets.',
            'source': 'Mayo Clinic Health',
            'url': 'https://www.mayoclinic.org/diseases-conditions/viral-gastroenteritis/diagnosis-treatment/drc-20378852',
            'urlToImage': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-09T13:10:00Z',
            'category': 'diarrhea',
        },
    ],
}

# In-memory cache: { (topic, limit): (timestamp, [articles]) }
_NEWS_CACHE = {}
CACHE_TTL_SECONDS = 1800  # 30 minutes


def _get_api_key():
    return os.environ.get('NEWS_API_KEY', '').strip()


def _get_topic_query(topic):
    topic = (topic or 'nutrition').lower()
    mapping = {
        'parenting': '("parenting tips" OR "child development" OR "positive parenting" OR "preschool parenting")',
        'nutrition': '("pediatric nutrition" OR "toddler healthy eating" OR "child diet" OR "infant feeding")',
        'safety': '("child safety tips" OR "babyproofing home" OR "pediatric injury prevention" OR "car seat safety")',
        'fever': '("child fever care" OR "pediatric fever management" OR "toddler temperature recovery")',
        'cough': '("pediatric cough relief" OR "toddler cough remedies" OR "child respiratory care")',
        'colds': '("toddler common cold" OR "child cold recovery" OR "pediatric runny nose congestion")',
        'diarrhea': '("child diarrhea hydration" OR "pediatric dehydration prevention" OR "toddler stomach bug")',
        'ailment': '("pediatric fever care" OR "toddler cold relief" OR "child hydration recovery")',
        'all': '("pediatric health" OR "healthy parenting tips" OR "child nutrition safety")',
    }
    return mapping.get(topic, mapping['all'])


def fetch_news_articles(topic='nutrition', limit=6):
    """
    Fetch articles for a topic using NewsAPI with in-memory caching and
    curated fallbacks if offline or rate-limited.
    """
    topic_key = (topic or 'all').lower()
    cache_key = (topic_key, limit)
    now = time.time()

    if cache_key in _NEWS_CACHE:
        cached_time, cached_articles = _NEWS_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS and cached_articles:
            return cached_articles

    api_key = _get_api_key()
    articles = []

    if api_key:
        try:
            query = _get_topic_query(topic_key)
            url = 'https://newsapi.org/v2/everything'
            params = {
                'q': query,
                'apiKey': api_key,
                'pageSize': max(limit, 10),
                'language': 'en',
                'sortBy': 'relevancy',
            }
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                raw_articles = data.get('articles', [])
                for item in raw_articles:
                    title = (item.get('title') or '').strip()
                    desc = (item.get('description') or '').strip()
                    if not title or title == '[Removed]' or desc == '[Removed]':
                        continue
                    
                    img = item.get('urlToImage')
                    if not img or not img.startswith('http'):
                        img = FALLBACK_IMAGES.get(topic_key, FALLBACK_IMAGES['general'])

                    source_name = item.get('source', {}).get('name') or 'Pediatric News'
                    published_raw = item.get('publishedAt') or ''
                    pub_formatted = 'Recently'
                    if published_raw:
                        try:
                            dt = datetime.fromisoformat(published_raw.replace('Z', '+00:00'))
                            pub_formatted = dt.strftime('%b %d, %Y')
                        except Exception:
                            pub_formatted = published_raw[:10]

                    articles.append({
                        'title': title,
                        'description': desc,
                        'source': source_name,
                        'url': item.get('url') or '#',
                        'urlToImage': img,
                        'publishedAt': pub_formatted,
                        'category': topic_key,
                    })

                    if len(articles) >= limit:
                        break
            else:
                logger.warning(f"NewsAPI responded with status {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"Error fetching from NewsAPI: {e}")

    # Fallback to curated articles if API returned empty or failed
    if not articles:
        fallback_pool = CURATED_FALLBACK_ARTICLES.get(topic_key)
        if not fallback_pool:
            if topic_key in ('fever', 'cough', 'colds', 'diarrhea', 'ailment'):
                fallback_pool = (
                    CURATED_FALLBACK_ARTICLES.get('fever', []) +
                    CURATED_FALLBACK_ARTICLES.get('colds', []) +
                    CURATED_FALLBACK_ARTICLES.get('cough', [])
                )
            else:
                fallback_pool = (
                    CURATED_FALLBACK_ARTICLES.get('parenting', []) +
                    CURATED_FALLBACK_ARTICLES.get('nutrition', []) +
                    CURATED_FALLBACK_ARTICLES.get('safety', [])
                )
        articles = list(fallback_pool)[:limit]

    _NEWS_CACHE[cache_key] = (now, articles)
    return articles


def determine_recommendation_context(child, user, session_topic=None):
    """
    Evaluates context priority:
    Priority 1 (Active Symptoms): Ailments logged in the last 72 hours
    Priority 2 (Parent Interest): Parent's module browsing / learning history
    Priority 3 (Baseline Default): Curated pediatric nutrition & safety
    """
    from models import FeverReading, RespiratoryEpisode, DiarrheaEpisode, ModuleProgress

    now = datetime.utcnow()
    window_start = now - timedelta(hours=72)

    # 1. Check Priority 1: Active symptoms logged in last 72h
    recent_fever = FeverReading.query.filter(
        FeverReading.child_id == child.id,
        FeverReading.recorded_at >= window_start
    ).order_by(FeverReading.recorded_at.desc(), FeverReading.id.desc()).first()

    recent_resp = RespiratoryEpisode.query.filter(
        RespiratoryEpisode.child_id == child.id,
        RespiratoryEpisode.recorded_at >= window_start
    ).order_by(RespiratoryEpisode.recorded_at.desc(), RespiratoryEpisode.id.desc()).first()

    recent_diarr = DiarrheaEpisode.query.filter(
        DiarrheaEpisode.child_id == child.id,
        DiarrheaEpisode.recorded_at >= window_start
    ).order_by(DiarrheaEpisode.recorded_at.desc(), DiarrheaEpisode.id.desc()).first()

    # Find the single most recent ailment
    ailments = []
    if recent_fever:
        ailments.append(('fever', recent_fever.recorded_at, recent_fever))
    if recent_resp:
        stype = 'cough' if recent_resp.symptom_type == 'cough' else 'colds'
        ailments.append((stype, recent_resp.recorded_at, recent_resp))
    if recent_diarr:
        ailments.append(('diarrhea', recent_diarr.recorded_at, recent_diarr))

    if ailments:
        ailments.sort(key=lambda x: x[1], reverse=True)
        chosen_ailment, rec_time, obj = ailments[0]
        
        badge_meta = {
            'fever': {
                'badge': f"Based on {child.name}'s recent Fever ({getattr(obj, 'value_celsius', 38.0):.1f}°C)",
                'icon': 'bi-thermometer-half',
                'topic': 'fever',
                'title': 'Active Symptom Care',
                'reason': f"Prioritizing recovery & hydration guides for {child.name}'s fever.",
            },
            'cough': {
                'badge': f"Based on {child.name}'s recent Cough log",
                'icon': 'bi-lungs-fill',
                'topic': 'cough',
                'title': 'Active Symptom Care',
                'reason': f"Pediatric respiratory care and comforting techniques for {child.name}.",
            },
            'colds': {
                'badge': f"Based on {child.name}'s recent Cold symptoms",
                'icon': 'bi-snow',
                'topic': 'colds',
                'title': 'Active Symptom Care',
                'reason': f"Gentle airway relief and recovery guidance for {child.name}.",
            },
            'diarrhea': {
                'badge': f"Based on {child.name}'s recent Diarrhea log",
                'icon': 'bi-droplet-half',
                'topic': 'diarrhea',
                'title': 'Active Symptom Care',
                'reason': f"Oral hydration & recovery nutrition recommendations for {child.name}.",
            },
        }
        meta = badge_meta.get(chosen_ailment, badge_meta['fever'])
        return {
            'priority': 1,
            'topic': meta['topic'],
            'badge_text': meta['badge'],
            'badge_icon': meta['icon'],
            'section_title': meta['title'],
            'reason': meta['reason'],
            'has_active_ailment': True,
            'ailment_type': chosen_ailment,
        }

    # 2. Check Priority 2: Parent module interaction
    topic_interest = session_topic
    if not topic_interest and user and user.is_authenticated:
        latest_prog = ModuleProgress.query.filter_by(user_id=user.id).order_by(
            ModuleProgress.updated_at.desc(), ModuleProgress.id.desc()
        ).first()
        if latest_prog and latest_prog.module and latest_prog.module.category in ('parenting', 'nutrition', 'safety'):
            topic_interest = latest_prog.module.category

    if topic_interest and topic_interest in ('parenting', 'nutrition', 'safety'):
        interest_meta = {
            'parenting': {
                'badge': 'Based on your interest in Parenting Guides',
                'icon': 'bi-people-fill',
                'topic': 'parenting',
                'title': 'Recommended Parenting Insights',
                'reason': 'Fresh evidence-based parenting strategies & early childhood development news.',
            },
            'nutrition': {
                'badge': 'Based on your interest in Child Nutrition',
                'icon': 'bi-apple',
                'topic': 'nutrition',
                'title': 'Recommended Nutrition Guidance',
                'reason': 'Pediatric diet, healthy eating milestones, and family mealtime insights.',
            },
            'safety': {
                'badge': 'Based on your interest in Child Safety',
                'icon': 'bi-shield-check',
                'topic': 'safety',
                'title': 'Recommended Safety & Childproofing Guides',
                'reason': 'Preventative child safety, home babyproofing, and developmental hazard prevention.',
            },
        }
        meta = interest_meta[topic_interest]
        return {
            'priority': 2,
            'topic': meta['topic'],
            'badge_text': meta['badge'],
            'badge_icon': meta['icon'],
            'section_title': meta['title'],
            'reason': meta['reason'],
            'has_active_ailment': False,
            'ailment_type': None,
        }

    # 3. Priority 3: Baseline default
    return {
        'priority': 3,
        'topic': 'nutrition',
        'badge_text': "Curated for your family's health & growth",
        'badge_icon': 'bi-stars',
        'section_title': 'Recommended for You',
        'reason': 'Top evidence-based pediatric health, nutrition, and safety updates.',
        'has_active_ailment': False,
        'ailment_type': None,
    }
