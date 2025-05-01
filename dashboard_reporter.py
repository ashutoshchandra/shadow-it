import json

def generate_report(saas_usage_data, output_file='saas_report.json'):
    with open(output_file, 'w') as f:
        json.dump(saas_usage_data, f, indent=2)

if __name__ == "__main__":
    sample_data = {
        "user1@corp.com": ["dropbox.com", "slack.com"],
        "user2@corp.com": ["notion.so"]
    }
    generate_report(sample_data)
