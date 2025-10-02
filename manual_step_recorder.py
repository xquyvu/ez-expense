"""
Simple MS Expense Manual Step Guide
Just tell me what you see and I'll help build the automation
"""

def manual_step_recorder():
    print("🎯 MS EXPENSE ITEMIZATION STEP RECORDER")
    print("=" * 50)
    print()
    print("I'll guide you through recording the steps manually.")
    print("Just describe what you see and do, and I'll capture the info.")
    print()
    
    steps = []
    step_num = 1
    
    print("Let's start! Please navigate to your MS Expense page:")
    print("https://myexpense.operations.dynamics.com/?cmp=1082&mi=ExpenseWorkspace")
    print()
    
    while True:
        print(f"\n--- STEP {step_num} ---")
        action = input("What did you just do? (or 'done' to finish): ")
        
        if action.lower() == 'done':
            break
            
        description = input("Describe what you see on screen now: ")
        
        # Ask for specific element info if they found something clickable
        element_info = ""
        if any(word in action.lower() for word in ['click', 'button', 'link', 'itemize']):
            element_info = input("Can you right-click -> Inspect Element and describe what you see? (optional): ")
        
        step = {
            'step': step_num,
            'action': action,
            'description': description,
            'element_info': element_info
        }
        
        steps.append(step)
        print(f"✅ Recorded step {step_num}")
        step_num += 1
    
    # Save results
    print("\n📋 RECORDED STEPS:")
    print("=" * 30)
    for step in steps:
        print(f"Step {step['step']}: {step['action']}")
        print(f"  Saw: {step['description']}")
        if step['element_info']:
            print(f"  Element: {step['element_info']}")
        print()
    
    # Save to file
    import json
    from datetime import datetime
    filename = f"ms_expense_manual_steps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(steps, f, indent=2)
    
    print(f"💾 Steps saved to: {filename}")
    
    return steps

if __name__ == "__main__":
    manual_step_recorder()