import re
import os
import glob

def format_log():
    # Find the latest short log
    logs = glob.glob("logs/*-short.log")
    if not logs:
        print("No short logs found.")
        return
    
    latest_log = max(logs, key=os.path.getmtime)
    output_md = latest_log.replace("-short.log", ".md")
    
    with open(latest_log, "r") as f:
        lines = f.readlines()

    md_content = f"# Adventure Log: {os.path.basename(latest_log).split('-')[1].capitalize()}\n"
    md_content += f"Generated on: {os.path.basename(latest_log).split('-')[0]}\n\n"
    
    current_node = None
    
    # Regex to capture node name and content from short log
    # Format: [NODE_NAME] Content...
    # Format: [NODE_NAME] (TOOL) tool_name(args)
    # Format: [SYSTEM] Result...
    line_pattern = re.compile(r'^\[(\w+)\]\s*(.*)', re.DOTALL)

    for line in lines:
        match = line_pattern.match(line)
        if not match:
            # Multi-line message continuation
            if line.strip():
                md_content += f"{line.strip()}\n\n"
            continue
            
        node_name, content = match.groups()
        content = content.strip()
        
        if not content:
            continue

        # Start a new section if the node changes (and it's not a SYSTEM message)
        if node_name != "SYSTEM" and node_name != current_node:
            current_node = node_name
            md_content += f"---\n## {current_node}\n\n"

        # Detect and format Tool Calls: (TOOL) tool_name(args)
        if content.startswith("(TOOL)"):
            tool_info = content.replace("(TOOL)", "").strip()
            md_content += f"> **🛠 Tool Call:** `{tool_info}`\n\n"
            continue

        # Format SYSTEM results
        if node_name == "SYSTEM":
            md_content += f"#### 📝 System Result\n_{content}_\n\n"
        else:
            # Regular message
            md_content += f"{content}\n\n"

    with open(output_md, "w") as f:
        f.write(md_content)
    
    print(f"Formatted log saved to: {output_md}")

if __name__ == "__main__":
    format_log()
