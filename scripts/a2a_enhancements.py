# auto_agent_discovery

# Auto-discover registered agents
def discover_agents():
    import requests
    resp = requests.get('http://10.118.155.218:8081/v1/agents/list')
    agents = resp.json()
    return agents.get('agents', [])


---
# load_balance

# Simple round-robin load balancer
class RoundRobin:
    def __init__(self, agents):
        self.agents = agents
        self.idx = 0
    
    def next(self):
        agent = self.agents[self.idx]
        self.idx = (self.idx + 1) % len(self.agents)
        return agent


---
# failure_fallback

# If agent dies, route to next available
def route_with_fallback(agent_actions, available_agents):
    for agent in available_agents:
        try:
            result = agent_actions(agent)
            return result
        except:
            continue
    return None


---
