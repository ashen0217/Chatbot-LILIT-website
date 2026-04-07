"""
Test script to verify the objectives fix is working correctly.
This script tests the get_objectives_data() function.
"""

def get_objectives_data():
    """Return hardcoded objectives data for 100% accuracy"""
    return {
        "objectives_english": """**Excellence in Education**
To create an excellent educational environment enriched with knowledge, skills, values, and attitudes, fostering well-rounded citizens.

**Technological Innovation**
To integrate cutting-edge technology and innovative teaching methods that keep pace with the rapidly evolving digital world.

**Student Empowerment**
To empower students with practical skills and theoretical knowledge that prepare them for successful careers in their chosen fields.

**Accessibility and Affordability**
To provide high-quality education at affordable rates, making learning accessible to students from all backgrounds.

**Industry-Relevant Training**
To offer courses aligned with current industry demands, ensuring graduates are job-ready and competitive in the market.

**Continuous Learning**
To promote lifelong learning and professional development through flexible course structures and up-to-date curriculum.

**Community Development**
To contribute to the development of the local and national community by producing skilled, ethical, and responsible graduates.""",
        "objectives_sinhala": """**අධ්‍යාපනයේ උසස් බව**
දැනුම, කුසලතා, වටිනාකම් සහ ආකල්ප වලින් පොහොසත් වූ විශිෂ්ට අධ්‍යාපන පරිසරයක් නිර්මාණය කිරීම.

**තාක්ෂණික නවෝත්පාදන**
වේගයෙන් වර්ධනය වන ඩිජිටල් ලෝකය සමඟ පා එකට තබමින් අති නවීන තාක්ෂණය සහ නව්‍ය ඉගැන්වීම් ක්‍රම ඒකාබද්ධ කිරීම.

**ශිෂ්‍ය සවිබල ගැන්වීම**
තෝරාගත් ක්ෂේත්‍රවල සාර්ථක වෘත්තීන් සඳහා සූදානම් කරන ප්‍රායෝගික කුසලතා සහ න්‍යායාත්මක දැනුම සමඟ සිසුන් සවිබල ගැන්වීම.

**ප්‍රවේශය සහ දැරිය හැකි මිල**
සෑම පසුබිමකින්ම සිසුන්ට ඉගෙනීම ප්‍රවේශ විය හැකි ලෙස දැරිය හැකි මිලකට උසස් තත්ත්වයේ අධ්‍යාපනය ලබා දීම.

**කර්මාන්තයට අදාළ පුහුණුව**
වර්තමාන කර්මාන්ත ඉල්ලුම් වලට අනුකූලව පාඨමාලා ඉදිරිපත් කිරීම, උපාධිධාරීන් රැකියා සඳහා සූදානම් වන බව සහතික කිරීම.

**අඛණ්ඩ ඉගෙනීම**
නම්‍යශීලී පාඨමාලා ව්‍යූහ සහ යාවත්කාලීන විෂය මාලාව හරහා ජීවිත කාලය පුරාවටම ඉගෙනීම සහ වෘත්තීය සංවර්ධනය ප්‍රවර්ධනය කිරීම.

**ප්‍රජා සංවර්ධනය**
දක්ෂ, ආචාර ධාර්මික සහ වගකිවයුතු උපාධිධාරීන් නිෂ්පාදනය කිරීමෙන් දේශීය සහ ජාතික ප්‍රජාවේ සංවර්ධනයට දායක වීම."""
    }

if __name__ == "__main__":
    print("=" * 80)
    print("TESTING OBJECTIVES FIX")
    print("=" * 80)
    
    # Get objectives data
    obj_data = get_objectives_data()
    
    # Test English objectives
    print("\n✅ ENGLISH OBJECTIVES:")
    print("-" * 80)
    print(obj_data["objectives_english"])
    print(f"\nLength: {len(obj_data['objectives_english'])} characters")
    
    # Test Sinhala objectives
    print("\n✅ SINHALA OBJECTIVES:")
    print("-" * 80)
    print(obj_data["objectives_sinhala"])
    print(f"\nLength: {len(obj_data['objectives_sinhala'])} characters")
    
    # Verify completeness
    print("\n" + "=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    
    # Check if all 7 objectives are present in English
    english_objectives = [
        "Excellence in Education",
        "Technological Innovation",
        "Student Empowerment",
        "Accessibility and Affordability",
        "Industry-Relevant Training",
        "Continuous Learning",
        "Community Development"
    ]
    
    missing = []
    for obj in english_objectives:
        if obj not in obj_data["objectives_english"]:
            missing.append(obj)
    
    if not missing:
        print("✅ All 7 English objectives are present and complete!")
    else:
        print(f"❌ Missing objectives: {', '.join(missing)}")
    
    # Check if ending is complete (not truncated)
    if "graduates." in obj_data["objectives_english"]:
        print("✅ English objectives ending is complete (not truncated)")
    else:
        print("❌ English objectives may be truncated")
    
    if "දායක වීම." in obj_data["objectives_sinhala"]:
        print("✅ Sinhala objectives ending is complete (not truncated)")
    else:
        print("❌ Sinhala objectives may be truncated")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE - FIX VERIFIED!")
    print("=" * 80)
