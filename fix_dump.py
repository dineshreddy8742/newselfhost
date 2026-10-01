import sys

print("Starting to process dump.sql line by line...")
with open("dump.sql", "r", encoding="utf-8", errors="ignore") as f_in, open("dump_fixed.sql", "w", encoding="utf-8") as f_out:
    for line in f_in:
        if "transaction_timeout" not in line:
            f_out.write(line)
print("Finished!")
