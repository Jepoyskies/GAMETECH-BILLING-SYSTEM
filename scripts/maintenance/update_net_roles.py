with open('network_manager/views.py', 'r') as f:
    content = f.read()

content = content.replace("@role_required(['Admin'])", "@role_required(['Admin', 'CSR'])")
content = content.replace("@role_required(['Admin', 'Editor'])", "@role_required(['Admin', 'Editor', 'CSR'])")

with open('network_manager/views.py', 'w') as f:
    f.write(content)

print("Done!")
