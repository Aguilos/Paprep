import os
import time
import random
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

# Rich curated fallback articles (multiple distinct batches of 6 per category)
CURATED_FALLBACK_ARTICLES = {
    'nutrition': [
        # Batch 1
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
        {
            'title': 'Vitamin D and Calcium: Bone Health Essentials for Growing Children',
            'description': 'How sunlight exposure, fortified dairy, and leafy greens together support peak bone density during the rapid growth years of early childhood.',
            'source': 'NIH Office of Dietary Supplements',
            'url': 'https://ods.od.nih.gov/factsheets/VitaminD-Consumer/',
            'urlToImage': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-07T08:45:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Hidden Sugar in Toddler Foods: Label Reading Made Simple',
            'description': 'Dietitians decode the 60+ names for added sugar on food labels and share practical swaps to reduce intake without eliminating enjoyment.',
            'source': 'Academy of Nutrition and Dietetics',
            'url': 'https://www.eatright.org/food/nutrition/dietary-guidelines-and-myplate/sugar-101',
            'urlToImage': 'https://images.unsplash.com/photo-1551632811-561732d1e306?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-05T14:00:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Introducing Allergenic Foods Early: What the LEAP Study Taught Us',
            'description': 'New evidence shows early, regular introduction of peanuts and eggs significantly reduces allergy risk in high-risk infants when done correctly.',
            'source': 'NIAID Allergy Research',
            'url': 'https://www.niaid.nih.gov/diseases-conditions/peanut-allergy',
            'urlToImage': 'https://images.unsplash.com/photo-1620706857370-e1b9770e8bb1?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-03T11:30:00Z',
            'category': 'nutrition',
        },
        # Batch 2
        {
            'title': 'Gut Health and Probiotics: Building Your Child\'s Microbiome',
            'description': 'Natural food sources of prebiotic fiber and probiotic cultures like yogurt and kefir that support immunity and healthy digestion in toddlers.',
            'source': 'Pediatric Gastroenterology Review',
            'url': 'https://www.healthychildren.org/English/healthy-living/nutrition/Pages/Probiotics.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-30T10:00:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Omega-3 DHA for Brain Development: Fish and Plant Sources',
            'description': 'Why fatty acids are crucial building blocks for retinal and brain tissue, plus safe low-mercury seafood recommendations for toddlers.',
            'source': 'American Heart Association Pediatrics',
            'url': 'https://www.eatright.org/food/nutrition/dietary-guidelines-and-myplate/fish-and-kids',
            'urlToImage': 'https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-26T14:15:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Transitioning to Cow\'s Milk or Plant Alternatives: What to Choose',
            'description': 'Comparing whole cow\'s milk, fortified soy milk, and oat beverages for fat, protein, and calcium content at the 12-month milestone.',
            'source': 'American Academy of Pediatrics',
            'url': 'https://www.healthychildren.org/English/healthy-living/nutrition/Pages/Recommended-Drinks-for-Young-Children-Ages-0-5.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-21T09:30:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Sensory-Friendly Mealtime: Overcoming Texture Aversions',
            'description': 'Occupational therapists offer low-pressure exposure ladders for children who struggle with slimy, crunchy, or mixed-texture foods.',
            'source': 'Child Mind Institute Nutrition',
            'url': 'https://childmind.org/article/selective-eating-children/',
            'urlToImage': 'https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-17T11:00:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Plant-Based Toddler Meals: Ensuring Complete Proteins',
            'description': 'How pairing beans, lentils, whole grains, and seeds ensures growing children receive all nine essential amino acids.',
            'source': 'Academy of Nutrition and Dietetics',
            'url': 'https://www.eatright.org/food/nutrition/vegetarian-and-special-diets/vegetarian-diets-for-children',
            'urlToImage': 'https://images.unsplash.com/photo-1551632811-561732d1e306?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-13T15:20:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Hydration Guidelines: How Much Water Does Your Toddler Need?',
            'description': 'Daily ounce recommendations by age group, recognizing mild dehydration, and creating fun water-infusion ideas without juice concentrate.',
            'source': 'CDC Healthy Schools and Early Care',
            'url': 'https://www.cdc.gov/nutrition/data-statistics/plain-water-the-healthier-choice.html',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-08T08:50:00Z',
            'category': 'nutrition',
        },
        # Batch 3
        {
            'title': 'Healthy Fats for Toddler Energy: Avocado, Nut Butters, and Olive Oil',
            'description': 'Why infants and young toddlers need roughly 40% of their daily calories from dietary fats to fuel rapid brain and cellular development.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/healthy-living/nutrition/Pages/Dietary-Fats-Good-vs-Bad.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-02T13:40:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Managing Food Refusal Without Power Struggles at the Family Table',
            'description': 'Pediatric psychologists explain how pressure to eat decreases appetite, while neutral exposure encourages curiosity and trying new vegetables.',
            'source': 'Zero to Three Nutrition',
            'url': 'https://www.zerotothree.org/resource/toddler-nutrition-and-picky-eating/',
            'urlToImage': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-28T10:15:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Snack Schedules That Support Steady Blood Sugar in Active Children',
            'description': 'Structuring balanced mid-morning and afternoon snacks with protein and complex carbs to prevent toddler meltdowns and energy crashes.',
            'source': 'Ellyn Satter Feeding Dynamics',
            'url': 'https://www.ellynsatterinstitute.org/family-meals-and-snacks/',
            'urlToImage': 'https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-24T16:00:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Choline and Folate: The Unsung Heroes of Early Neurodevelopment',
            'description': 'Egg yolks, liver, poultry, and beans provide choline that supports memory centers in developing brains during the first 1,000 days.',
            'source': 'NIH Office of Dietary Supplements',
            'url': 'https://ods.od.nih.gov/factsheets/Choline-Consumer/',
            'urlToImage': 'https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-19T11:20:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Homemade vs. Store-Bought Baby Food: Nutritional Comparisons',
            'description': 'A neutral guide evaluating commercial pouches against fresh home preparation, focusing on texture progression and micronutrient retention.',
            'source': 'American Academy of Pediatrics',
            'url': 'https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/Homemade-Baby-Food.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-15T09:10:00Z',
            'category': 'nutrition',
        },
        {
            'title': 'Zinc for Immune Resilience: Serving Seeds, Meats, and Legumes',
            'description': 'How zinc deficiency impairs epithelial repair and immune defense in young toddlers, plus kid-approved recipes to boost absorption.',
            'source': 'Pediatric Clinical Nutrition',
            'url': 'https://www.eatright.org/food/vitamins-and-supplements/nutrient-rich-foods/zinc',
            'urlToImage': 'https://images.unsplash.com/photo-1551632811-561732d1e306?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-10T14:30:00Z',
            'category': 'nutrition',
        },
    ],
    'parenting': [
        # Batch 1
        {
            'title': 'Positive Parenting: Building Emotional Resilience in Young Children',
            'description': 'Child psychologists share core techniques for validating toddlers\' emotions while setting calm, consistent developmental boundaries at home.',
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
        {
            'title': 'Screen Time and Young Children: Evidence-Based Limits by Age',
            'description': 'Updated guidance from pediatric associations on how much screen time is appropriate for infants, toddlers, and preschoolers and what content matters most.',
            'source': 'American Academy of Pediatrics',
            'url': 'https://www.healthychildren.org/English/family-life/Media/Pages/Where-We-Stand-TV-Viewing-Time.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1587240602618-4a10bb16f8b2?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-06T09:00:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Sleep Training Methods Compared: What the Research Actually Says',
            'description': 'A neutral look at graduated extinction, bedtime fading, and no-cry approaches, with outcomes data for infant sleep duration and parent wellbeing.',
            'source': 'Sleep Foundation Pediatrics',
            'url': 'https://www.sleepfoundation.org/baby-sleep/sleep-training',
            'urlToImage': 'https://images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-04T07:30:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Building Secure Attachment: Simple Daily Habits That Make a Difference',
            'description': 'Responsive caregiving, eye contact, and predictable routines in the first three years lay the neurological groundwork for trust and emotional security.',
            'source': 'Zero to Three',
            'url': 'https://www.zerotothree.org/resource/attachment-and-bonding/',
            'urlToImage': 'https://images.unsplash.com/photo-1606092195730-5d7b9af1efc5?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-02T10:00:00Z',
            'category': 'parenting',
        },
        # Batch 2
        {
            'title': 'Fostering Independence in Preschoolers: Chores and Daily Choices',
            'description': 'Empowering toddlers and preschoolers with age-appropriate responsibility fosters intrinsic confidence, problem solving, and cooperativeness.',
            'source': 'Child Development Institute',
            'url': 'https://www.zerotothree.org/resource/fostering-independence-in-early-childhood/',
            'urlToImage': 'https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-28T09:15:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Social-Emotional Milestones: How Toddlers Learn Empathy and Sharing',
            'description': 'Insights into the neurobiology of early childhood friendships, turn-taking development, and guiding toddlers through conflict peacefully.',
            'source': 'American Psychological Association',
            'url': 'https://www.apa.org/topics/parenting/emotion-regulation',
            'urlToImage': 'https://images.unsplash.com/photo-1485546246426-74dc88dec4d9?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-25T11:40:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Separation Anxiety in Early Childhood: Gentle Transition Techniques',
            'description': 'Pediatric strategies for smooth daycare drop-offs, reassuring goodbye rituals, and helping your child develop internal coping mechanisms.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/ages-stages/toddler/Pages/Soothing-Your-Childs-Separation-Anxiety.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1476703993599-0035a21b17a9?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-22T08:20:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Sibling Rivalry and New Baby Adjustments: Preparing Your Child',
            'description': 'Actionable steps to help an older sibling feel valued and secure when welcoming a newborn brother or sister into the household.',
            'source': 'Seattle Children\'s Hospital',
            'url': 'https://www.seattlechildrens.org/health-safety/keeping-kids-healthy/development/sibling-rivalry/',
            'urlToImage': 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-18T13:00:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Speech and Language Milestones: When to Seek Speech Therapy',
            'description': 'A clear developmental guide tracking phoneme production, vocabulary count, and sentence formation from 12 to 36 months.',
            'source': 'ASHA Pediatric Speech',
            'url': 'https://www.asha.org/public/speech/development/',
            'urlToImage': 'https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-15T10:10:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Constructive Discipline: Replacing Time-Outs with Connection',
            'description': 'Why neuroscientists suggest collaborative problem-solving over isolation when helping dysregulated young children understand household boundaries.',
            'source': 'Harvard Center on the Developing Child',
            'url': 'https://developingchild.harvard.edu/resources/inbrief-the-science-of-early-childhood-development/',
            'urlToImage': 'https://images.unsplash.com/photo-1606092195730-5d7b9af1efc5?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-12T14:30:00Z',
            'category': 'parenting',
        },
        # Batch 3
        {
            'title': 'Outdoor Nature Play: Cognitive and Sensory Benefits for Toddlers',
            'description': 'How free exploration in mud, grass, and open parks develops proprioception, executive function, and lowers early stress hormone levels.',
            'source': 'National Association for the Education of Young Children',
            'url': 'https://www.naeyc.org/resources/pubs/yc/may2019/nature-play-outdoors',
            'urlToImage': 'https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-06T09:00:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Preventing Parental Burnout: Restoring Emotional Bandwidth',
            'description': 'Practical boundaries, micro-moments of self-care, and partner communication to preserve empathy and patience during high-stress parenting phases.',
            'source': 'American Psychological Association',
            'url': 'https://www.apa.org/topics/parenting/burnout',
            'urlToImage': 'https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-01T15:20:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Potty Training Readiness: Recognizing Physical & Behavioral Signs',
            'description': 'Why pushing potty training before developmental readiness causes setbacks, and how child-led pacing creates confidence without anxiety.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/ages-stages/toddler/toilet-training/Pages/default.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-27T11:45:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Music and Rhythm in Early Childhood: Wiring Brains for Math & Language',
            'description': 'Daily singing, clapping games, and exposure to varied musical cadences enhance auditory processing and phonetic awareness in early childhood.',
            'source': 'Zero to Three Child Development',
            'url': 'https://www.zerotothree.org/resource/music-and-toddlers/',
            'urlToImage': 'https://images.unsplash.com/photo-1587240602618-4a10bb16f8b2?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-22T08:30:00Z',
            'category': 'parenting',
        },
        {
            'title': 'Managing Night Fears and Separation at Bedtime: Warm Rituals',
            'description': 'Transforming nighttime protests into calming connection through transitional objects, dim lighting routines, and low-stimulus storytelling.',
            'source': 'Child Mind Institute',
            'url': 'https://childmind.org/article/bedtime-problems-in-young-children/',
            'urlToImage': 'https://images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-17T13:00:00Z',
            'category': 'parenting',
        },
        {
            'title': 'The Power of Unstructured Play: Building Imagination and Grit',
            'description': 'Why open-ended play with cardboard boxes and blocks fosters far greater problem-solving resilience than rigid, rule-based structured activities.',
            'source': 'Harvard Graduate School of Education',
            'url': 'https://www.gse.harvard.edu/ideas/ed-magazine/play-critical-child-development',
            'urlToImage': 'https://images.unsplash.com/photo-1485546246426-74dc88dec4d9?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-12T10:10:00Z',
            'category': 'parenting',
        },
    ],
    'safety': [
        # Batch 1
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
        {
            'title': 'Car Seat Safety by Age and Weight: Installing It Right',
            'description': 'Updated guidelines on rear-facing, forward-facing, booster, and seat-belt transitions, plus proper installation angle and harness tightness checks.',
            'source': 'National Highway Traffic Safety Administration',
            'url': 'https://www.nhtsa.gov/equipment/car-seats-and-booster-seats',
            'urlToImage': 'https://images.unsplash.com/photo-1591018533626-0bb5eb30fbfb?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-11T09:00:00Z',
            'category': 'safety',
        },
        {
            'title': 'Choking Hazard Guide: Foods and Objects to Avoid Under Age 4',
            'description': 'A detailed breakdown of high-risk foods by texture and size, plus how to perform back blows and abdominal thrusts on infants and toddlers.',
            'source': 'American Red Cross',
            'url': 'https://www.redcross.org/take-a-class/resources/articles/infant-choking',
            'urlToImage': 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-09T12:30:00Z',
            'category': 'safety',
        },
        {
            'title': 'Sun Safety for Infants and Toddlers: SPF, Shade, and Timing',
            'description': 'Why sunscreen is not recommended under 6 months, and the shade-and-cover strategy pediatricians recommend for protecting sensitive skin outdoors.',
            'source': 'Skin Cancer Foundation',
            'url': 'https://www.skincancer.org/skin-cancer-prevention/sun-protection/children-and-sun-protection/',
            'urlToImage': 'https://images.unsplash.com/photo-1520637836862-4d197d17c93a?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-07T10:15:00Z',
            'category': 'safety',
        },
        # Batch 2
        {
            'title': 'Burn and Scald Prevention: Kitchen and Water Heater Safety',
            'description': 'Setting household water heaters below 120°F (49°C), stove knob guards, and establishing a three-foot toddler-free zone around ovens.',
            'source': 'Safe Kids Worldwide',
            'url': 'https://www.safekids.org/safetytips/field_risks/burns-and-scalds',
            'urlToImage': 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-29T12:00:00Z',
            'category': 'safety',
        },
        {
            'title': 'Pediatric First Aid Kit: What Every Family Home Needs',
            'description': 'Pediatrician-curated checklist of bandages, thermometers, antiseptic solutions, antihistamines, and emergency poison control contact cards.',
            'source': 'American Academy of Pediatrics',
            'url': 'https://www.healthychildren.org/English/safety-prevention/at-home/Pages/First-Aid-Kit-Chock-Full-of-Useful-Items.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-24T16:00:00Z',
            'category': 'safety',
        },
        {
            'title': 'Window and Balcony Safety: Proven Guards and Locks',
            'description': 'Why window screens are not designed to stop falls, and how certified 4-inch stop-locks prevent high-risk falls in multistory homes.',
            'source': 'National Safety Council',
            'url': 'https://www.nsc.org/community-safety/safety-topics/child-safety/window-safety',
            'urlToImage': 'https://images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-19T08:30:00Z',
            'category': 'safety',
        },
        {
            'title': 'Household Poison Control: Securing Medicines and Cleaners',
            'description': 'Storing prescription medicines out of reach and sight, child-resistant caps, and immediate steps if a child ingests a cleaning compound.',
            'source': 'American Association of Poison Control Centers',
            'url': 'https://www.poison.org/articles/keep-kids-safe-from-household-poisons',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-14T11:45:00Z',
            'category': 'safety',
        },
        {
            'title': 'Button Battery and Magnet Hazards: Critical Warning for Parents',
            'description': 'High-power button batteries and neodymium magnets create severe internal tissue erosion within two hours if swallowed. Here\'s what to secure.',
            'source': 'CPSC Child Safety',
            'url': 'https://www.cpsc.gov/Safety-Education/Safety-Education-Centers/Button-Battery-Safety',
            'urlToImage': 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-10T14:20:00Z',
            'category': 'safety',
        },
        {
            'title': 'Playground and Helmet Safety: Preventing Head Injuries',
            'description': 'Guidelines on impact-absorbing wood mulch or rubber surfacing, properly fitted multi-sport helmets, and supervision during climbing play.',
            'source': 'CDC Injury Prevention',
            'url': 'https://www.cdc.gov/heads-up/parents/index.html',
            'urlToImage': 'https://images.unsplash.com/photo-1520637836862-4d197d17c93a?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-05T09:10:00Z',
            'category': 'safety',
        },
        # Batch 3
        {
            'title': 'Toy Safety and Recall Checks: Avoiding Hidden Hazards',
            'description': 'Verifying age labels on packaging, avoiding small parts under 3 years old, and checking monthly consumer product recall registers.',
            'source': 'US Consumer Product Safety Commission',
            'url': 'https://www.cpsc.gov/Recalls',
            'urlToImage': 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-30T10:00:00Z',
            'category': 'safety',
        },
        {
            'title': 'Pet Interaction Safety: Teaching Gentle Touch and Space',
            'description': 'Never leaving infants or toddlers alone with family pets, reading canine stress signals, and establishing safe feeding zones for animals.',
            'source': 'Humane Society & AAP',
            'url': 'https://www.healthychildren.org/English/safety-prevention/all-around/Pages/Animals-and-Your-Child.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1508873696983-2df5293cb32f?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-25T14:30:00Z',
            'category': 'safety',
        },
        {
            'title': 'Fire and Carbon Monoxide Safety: Home Drills and Alarm Audits',
            'description': 'Testing interconnected smoke and CO detectors monthly, fire escape ladder placement, and teaching toddlers to get low and exit calmly.',
            'source': 'National Fire Protection Association',
            'url': 'https://www.nfpa.org/education-and-research/home-fire-safety',
            'urlToImage': 'https://images.unsplash.com/photo-1519689680058-324335c77eba?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-20T11:15:00Z',
            'category': 'safety',
        },
        {
            'title': 'Electrical Cord and Outlet Safety: Concealing Home Wiring',
            'description': 'Tamper-resistant receptacle covers, eliminating hanging curtain cords, and securing power strips inside enclosed wire organizers.',
            'source': 'Electrical Safety Foundation',
            'url': 'https://www.esfi.org/home-safety/child-safety/',
            'urlToImage': 'https://images.unsplash.com/photo-1591018533626-0bb5eb30fbfb?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-16T08:40:00Z',
            'category': 'safety',
        },
        {
            'title': 'Driveway and Garage Safety: Eliminating Blind Zone Hazards',
            'description': 'Walking completely around vehicles before reversing, holding toddler hands in parking areas, and testing automatic garage door reversal sensors.',
            'source': 'KidsAndCars.org',
            'url': 'https://www.kidsandcars.org/how-kids-get-hurt/backovers',
            'urlToImage': 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-11T13:20:00Z',
            'category': 'safety',
        },
        {
            'title': 'Insect Repellents for Kids: Safe DEET and Picaridin Usage',
            'description': 'Selecting appropriate repellent concentrations, applying only to outer clothing and exposed skin, and washing off before bedtime.',
            'source': 'AAP Environmental Health',
            'url': 'https://www.healthychildren.org/English/safety-prevention/at-play/Pages/Insect-Repellents.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1520637836862-4d197d17c93a?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-06T09:50:00Z',
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
            'source': 'Children\'s Hospital Health',
            'url': 'https://www.seattlechildrens.org/conditions/a-z/fever/',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-12T11:00:00Z',
            'category': 'fever',
        },
        {
            'title': 'Febrile Seizures: Causes, Warning Signs, and Emergency First Aid',
            'description': 'While frightening to witness, most febrile seizures cause no long-term harm. Pediatric neurologists walk through exact response steps.',
            'source': 'National Institute of Neurological Disorders',
            'url': 'https://www.ninds.nih.gov/health-information/disorders/febrile-seizures',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-10-01T08:15:00Z',
            'category': 'fever',
        },
        {
            'title': 'When to Call the Doctor for a Fever: Age-by-Age Guide',
            'description': 'Specific temperature thresholds for infants under 3 months, toddlers, and older kids, plus behavioral red flags requiring pediatric care.',
            'source': 'Mayo Clinic Pediatrics',
            'url': 'https://www.mayoclinic.org/diseases-conditions/fever/in-depth/fever/art-20050997',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-23T14:40:00Z',
            'category': 'fever',
        },
        {
            'title': 'Acetaminophen vs. Ibuprofen: Weight-Based Dosing Safety',
            'description': 'Why weight is far more accurate than age when measuring antipyretic suspensions, and why alternating medications requires pediatric clearance.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/safety-prevention/at-home/medication-safety/Pages/How-to-Take-a-Childs-Temperature.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-16T10:00:00Z',
            'category': 'fever',
        },
        {
            'title': 'Dressing a Feverish Child: Why Bundling Up Can Be Dangerous',
            'description': 'Pediatricians explain how excessive blankets trap radiant body heat and elevate core temperature, recommending light cotton clothing instead.',
            'source': 'Cincinnati Children\'s Hospital',
            'url': 'https://www.cincinnatichildrens.org/health/f/fever',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-11T12:20:00Z',
            'category': 'fever',
        },
        {
            'title': 'Sponge Baths and Fever: Why Lukewarm Water is Mandatory',
            'description': 'Never use cold water, rubbing alcohol, or ice baths, which trigger violent shivering that drives internal body temperature even higher.',
            'source': 'Children\'s Hospital of Philadelphia',
            'url': 'https://www.chop.edu/conditions-diseases/fever-children',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-04T09:30:00Z',
            'category': 'fever',
        },
        {
            'title': 'Understanding Biphasic Fevers: When Temperatures Spike Again',
            'description': 'Why common childhood viral illnesses often have a brief temperature respite before a second milder peak during normal immune resolution.',
            'source': 'AAP Infectious Diseases',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/fever/Pages/When-to-Call-the-Pediatrician.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-26T15:15:00Z',
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
        {
            'title': 'Nighttime Cough Relief: Elevation and Ultrasonic Humidifiers',
            'description': 'How cool-mist humidification soothes swollen bronchial tissues and prevents dry airway spasms during sleep without medication.',
            'source': 'Children\'s National Hospital',
            'url': 'https://childrensnational.org/visit/conditions-and-treatments/airway-lungs/cough',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-27T15:10:00Z',
            'category': 'cough',
        },
        {
            'title': 'Wheezing and Bronchiolitis: When Cough Signals Airway Restriction',
            'description': 'Understanding RSV and bronchiolitis in toddlers, monitoring respiratory rates, and recognizing when inhaler therapy or oxygen is needed.',
            'source': 'CDC Respiratory Viruses',
            'url': 'https://www.cdc.gov/rsv/infants-young-children/index.html',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-20T11:45:00Z',
            'category': 'cough',
        },
        {
            'title': 'Post-Viral Lingering Cough: Expected Recovery Timelines',
            'description': 'Why a sensitive airway cough can persist for 3 to 4 weeks after an infection has cleared, and how to tell if it has turned into pneumonia.',
            'source': 'American Lung Association',
            'url': 'https://www.lung.org/lung-health-diseases/lung-disease-lookup/coughs/coughs-in-children',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-15T09:00:00Z',
            'category': 'cough',
        },
        {
            'title': 'Recognizing Respiratory Distress: Retractions and Nasal Flaring',
            'description': 'A visual guide for parents on identifying work of breathing: belly breathing, sternal retractions, and grunting that require urgent care.',
            'source': 'Seattle Children\'s Emergency Care',
            'url': 'https://www.seattlechildrens.org/conditions/a-z/breathing-difficulty/',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-07T13:30:00Z',
            'category': 'cough',
        },
        {
            'title': 'Allergy Cough vs. Viral Infection: Differentiating Triggers',
            'description': 'Clear mucus, itchy watery eyes, and lack of fever often point toward seasonal allergens or pet dander rather than contagious viral colds.',
            'source': 'American College of Allergy, Asthma & Immunology',
            'url': 'https://acaai.org/allergies/allergic-conditions/cough/',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-31T11:00:00Z',
            'category': 'cough',
        },
        {
            'title': 'Hydration Strategies to Thin Viscous Airway Mucus Naturally',
            'description': 'Warm clear broths, diluted apple juice, and breastmilk lubricate the posterior pharynx and naturally loosen thick mucus plugs in small airways.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/chest-lungs/Pages/Caring-for-Your-Childs-Cold-or-Flu.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-21T14:10:00Z',
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
        {
            'title': 'Ear Infection Signs After a Cold: When to Check With an ENT',
            'description': 'Ear tugging, irritability while lying flat, and renewed fever after cold symptoms improve can indicate acute otitis media.',
            'source': 'AAP Ear Health',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/ear-nose-throat/Pages/Middle-Ear-Infections.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-28T16:15:00Z',
            'category': 'colds',
        },
        {
            'title': 'Soothing Sore Throats: Warm Broths, Fruit Popsicles and Hydration',
            'description': 'Simple cold and warm soothing therapies that numb irritated pharyngeal tissues and maintain fluid intake during upper viral infections.',
            'source': 'Mayo Clinic Health',
            'url': 'https://www.mayoclinic.org/diseases-conditions/sore-throat/diagnosis-treatment/drc-20351640',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-22T10:30:00Z',
            'category': 'colds',
        },
        {
            'title': 'Preventing Secondary Infections: Hand Hygiene for Littles',
            'description': 'Fun games and song routines that make handwashing effective and enjoyable, reducing the spread of rhinovirus in home environments.',
            'source': 'World Health Organization',
            'url': 'https://www.who.int/campaigns/world-hand-hygiene-day',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-17T14:00:00Z',
            'category': 'colds',
        },
        {
            'title': 'Sleep Strategies for Congested Toddlers: Positioning and Vapor',
            'description': 'Why slight head elevation and pre-bed warm steam baths help congested toddlers breathe comfortably through their noses at night.',
            'source': 'Sleep Foundation Pediatrics',
            'url': 'https://www.sleepfoundation.org/baby-sleep/sick-baby-sleep',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-09T08:00:00Z',
            'category': 'colds',
        },
        {
            'title': 'Nasal Bulb vs. Electric Nasal Aspirator: Safe Suctioning Limits',
            'description': 'How over-suctioning can inflame sensitive nasal mucosa, and why capping suction sessions at three times daily protects nasal tissues.',
            'source': 'AAP Ear, Nose & Throat Guidelines',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/ear-nose-throat/Pages/default.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-29T12:00:00Z',
            'category': 'colds',
        },
        {
            'title': 'Protecting Chapped Lips and Noses During Winter Viral Colds',
            'description': 'Applying a thin film of pure medical-grade petroleum jelly or breastmilk around irritated nostrils prevents painful excoriation.',
            'source': 'Pediatric Dermatology Review',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/skin/Pages/default.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-18T16:20:00Z',
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
        {
            'title': 'Rotavirus and Norovirus in Toddlers: Containment and Disinfection',
            'description': 'Effective cleaning protocols with chlorine bleach dilution, hand hygiene, and food safety measures to prevent household transmission.',
            'source': 'CDC Viral Gastroenteritis',
            'url': 'https://www.cdc.gov/norovirus/index.html',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-26T12:00:00Z',
            'category': 'diarrhea',
        },
        {
            'title': 'Recognizing Severe Dehydration: Tears, Diapers, and Fontanelle',
            'description': 'Clinical markers of dehydration in young children: lack of tears when crying, fewer than 3 wet diapers in 24 hours, and lethargy.',
            'source': 'AAP Pediatric Emergency Guidance',
            'url': 'https://www.healthychildren.org/English/health-issues/injuries-emergencies/Pages/Dehydration.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-18T10:15:00Z',
            'category': 'diarrhea',
        },
        {
            'title': 'Probiotics During Diarrhea: Shortening the Duration of Symptoms',
            'description': 'Clinical trials demonstrate specific strains like Lactobacillus rhamnosus GG can reduce viral diarrhea duration by up to 24 hours.',
            'source': 'European Society for Paediatric Gastroenterology (ESPGHAN)',
            'url': 'https://www.espghan.org/guidelines',
            'urlToImage': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-12T15:30:00Z',
            'category': 'diarrhea',
        },
        {
            'title': 'When Diarrhea Requires Stool Testing: Warning Signs to Watch For',
            'description': 'Blood or mucus in stools, persistent high fever, or symptoms lasting over 7 days warrant microbiological testing and pediatric review.',
            'source': 'Johns Hopkins Medicine',
            'url': 'https://www.hopkinsmedicine.org/health/conditions-and-diseases/diarrhea-in-children',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-09-06T09:40:00Z',
            'category': 'diarrhea',
        },
        {
            'title': 'Diaper Rash Care During Diarrhea: Thick Barrier Protection',
            'description': 'Frequent diaper changes, rinsing with plain warm water instead of wipes, and thick zinc oxide paste application prevent acid burns.',
            'source': 'HealthyChildren.org',
            'url': 'https://www.healthychildren.org/English/ages-stages/baby/diapers-clothing/Pages/Diaper-Rash.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-27T13:00:00Z',
            'category': 'diarrhea',
        },
        {
            'title': 'Why Anti-Diarrheal Medications Are Strictly Avoided in Children',
            'description': 'Pediatricians explain how medications like loperamide paralyze intestinal motility and can lead to toxic megacolon in young children.',
            'source': 'AAP Pediatric Pharmacology',
            'url': 'https://www.healthychildren.org/English/health-issues/conditions/abdominal/Pages/Diarrhea.aspx',
            'urlToImage': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
            'publishedAt': '2026-08-14T10:45:00Z',
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


def fetch_news_articles(topic='nutrition', limit=6, auto_refresh=False, exclude_titles=None):
    """
    Fetch articles for a topic using NewsAPI with in-memory caching and
    curated fallbacks if offline or rate-limited.
    Supports auto_refresh and exclude_titles to guarantee genuinely new articles
    on each timer trigger or tab switch.
    """
    topic_key = (topic or 'all').lower()
    now = time.time()

    # Parse excluded titles if provided
    exclude_set = set()
    if exclude_titles:
        if isinstance(exclude_titles, str):
            exclude_set = {t.strip().lower() for t in exclude_titles.split('|||') if t.strip()}
        elif isinstance(exclude_titles, (list, tuple, set)):
            exclude_set = {str(t).strip().lower() for t in exclude_titles if str(t).strip()}

    cache_key = (topic_key, limit)
    # Only return cache if not auto-refreshing and no specific excluded titles requested
    if not auto_refresh and not exclude_set and cache_key in _NEWS_CACHE:
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
                'pageSize': max(limit * 3, 30),
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
                    if title.lower() in exclude_set:
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
        # Build comprehensive pool for the topic
        if topic_key == 'all':
            fallback_pool = (
                CURATED_FALLBACK_ARTICLES.get('nutrition', []) +
                CURATED_FALLBACK_ARTICLES.get('parenting', []) +
                CURATED_FALLBACK_ARTICLES.get('safety', [])
            )
        elif topic_key in ('fever', 'cough', 'colds', 'diarrhea', 'ailment'):
            if topic_key in CURATED_FALLBACK_ARTICLES:
                fallback_pool = list(CURATED_FALLBACK_ARTICLES[topic_key])
                for other in ('fever', 'colds', 'cough', 'diarrhea'):
                    if other != topic_key:
                        fallback_pool.extend(CURATED_FALLBACK_ARTICLES.get(other, []))
            else:
                fallback_pool = (
                    CURATED_FALLBACK_ARTICLES.get('fever', []) +
                    CURATED_FALLBACK_ARTICLES.get('colds', []) +
                    CURATED_FALLBACK_ARTICLES.get('cough', []) +
                    CURATED_FALLBACK_ARTICLES.get('diarrhea', [])
                )
        else:
            fallback_pool = list(CURATED_FALLBACK_ARTICLES.get(topic_key, []))
            if len(fallback_pool) < limit:
                for other in ('nutrition', 'parenting', 'safety'):
                    if other != topic_key:
                        fallback_pool.extend(CURATED_FALLBACK_ARTICLES.get(other, []))

        # Filter out excluded titles if any
        if exclude_set:
            fresh_candidates = [
                a for a in fallback_pool
                if (a.get('title') or '').strip().lower() not in exclude_set
            ]
            if len(fresh_candidates) >= limit:
                articles = fresh_candidates[:limit]
            else:
                # If fresh pool exhausted, take all fresh candidates plus remaining items from pool
                seen_titles = {(a.get('title') or '').strip().lower() for a in fresh_candidates}
                remaining = [
                    a for a in fallback_pool
                    if (a.get('title') or '').strip().lower() not in seen_titles
                ]
                articles = (fresh_candidates + remaining)[:limit]
        elif auto_refresh:
            # If auto-refresh without explicit exclusions, shuffle or rotate
            shuffled = list(fallback_pool)
            random.seed(int(time.time() // 60))  # Consistent within the minute, changes each minute
            random.shuffle(shuffled)
            articles = shuffled[:limit]
        else:
            articles = list(fallback_pool)[:limit]

    if not auto_refresh and not exclude_set:
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
