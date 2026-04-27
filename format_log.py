import re
import os
import glob

def format_log():
    # Find the latest short log
    logs = glob.glob("logs/**/*-short.log", recursive=True)
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
    line_pattern = re.compile(r'^\[([^\]]+)\]\s*(.*)', re.DOTALL)

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

        # Handle special markers
        if node_name == "PARTY_STATUS":
            md_content += f"### 🛡 Party Status\n\n"
            chars = content.split(" | ")
            for char in chars:
                md_content += f"- **{char}**\n"
            md_content += "\n"
            continue
        
        if node_name == "INVENTORY":
            if "### 🎒 Equipment & Resources" not in md_content.split('\n')[-20:]:
                md_content += f"### 🎒 Equipment & Resources\n"
            md_content += f"- **Inventory** {content}\n"
            continue

        if node_name == "POWERS":
            if "### 🎒 Equipment & Resources" not in md_content.split('\n')[-20:]:
                md_content += f"### 🎒 Equipment & Resources\n"
            md_content += f"- **Powers** {content}\n"
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

    # Clean up
    md_content = md_content.replace("### 🎒 Equipment & Resources\n###", "###")

    with open(output_md, "w") as f:
        f.write(md_content)
    
    print(f"Formatted log saved to: {output_md}")

if __name__ == "__main__":
    format_log()
