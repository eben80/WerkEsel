import scout
import matcher
import tailor
from db_utils import setup_db

def main():
    print("🌟 WerkEsel Global Workflow Starting...")
    setup_db()

    # 1. Scout all active profiles
    print("\n--- Phase 1: Scouting ---")
    scout.run_scout_all()

    # 2. Match all unscored jobs
    print("\n--- Phase 2: Matching ---")
    matcher.run_matcher()

    # 3. Tailor all approved jobs
    print("\n--- Phase 3: Tailoring ---")
    tailor.run_tailor()

    print("\n✅ WerkEsel Global Workflow Complete.")

if __name__ == "__main__":
    main()
