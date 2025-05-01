import json

# Example list of known SaaS domains (can be enriched from APIs like SaaSDB, Cisco Umbrella)
KNOWN_SAAS_DOMAINS = ['dropbox.com', 'slack.com', 'zoom.us', 'notion.so', 'trello.com']

def is_saas_domain(domain):
    return any(domain.endswith(saas) for saas in KNOWN_SAAS_DOMAINS)

def analyze_domains(domains):
    return [d for d in domains if is_saas_domain(d)]

if __name__ == "__main__":
    domains = ['example.com', 'slack.com', 'internal.corp', 'zoom.us']
    print(analyze_domains(domains))  # ['slack.com', 'zoom.us']
