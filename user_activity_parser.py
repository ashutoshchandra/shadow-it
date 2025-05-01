import re

def extract_domains_from_logs(log_file):
    pattern = re.compile(r'https?://([a-zA-Z0-9.-]+)')
    domains = set()
    with open(log_file, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                domains.add(match.group(1))
    return list(domains)

if __name__ == "__main__":
    domains = extract_domains_from_logs('proxy.log')
    print(domains)
