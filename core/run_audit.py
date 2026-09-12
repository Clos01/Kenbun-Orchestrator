from tools.gui.tars_closed_loop_runtime import ClosedLoopGUIAgent
import time

def run():
    agent = ClosedLoopGUIAgent(endpoint='http://<REMOTE_HOST_IP>:8090/v1/chat/completions')
    task = "Audit the UI in the center of the screen. Look for the Client App app. Give an audit of how the app is used, where buttons are, rate the ease of use/complexity, and list possible confusions someone might have."
    
    print(f"Starting TARS Loop for Task: {task}")
    for i in range(15):
        print(f"\n--- STEP {i+1} ---")
        result = agent.step(task)
        print(f"Result from model: {result}")
        if result.get("action_type") == "call_user" or result.get("status") == "error":
            print(f"Finished: {result}")
            break
        elif result.get("error"):
            print(f"Error: {result.get('error')}")
            break
        time.sleep(2)

if __name__ == "__main__":
    run()
