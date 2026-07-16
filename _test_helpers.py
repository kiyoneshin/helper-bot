from cogs.staff_leaderboard import _generate_month_options, _month_value_to_range

opts = _generate_month_options()
print(f"Total options: {len(opts)}")
for o in opts[:5]:
    print(f"  {o.label} -> {o.value}")
print("  ...")
for o in opts[-3:]:
    print(f"  {o.label} -> {o.value}")

print()
dt_s, dt_e = _month_value_to_range("10-2025", "01-2026")
print(f"Range: {dt_s} -> {dt_e}")

# Test lỗi logic xuyên năm ngược
try:
    _month_value_to_range("03-2026", "12-2025")
    print("ERROR: should have raised ValueError")
except ValueError as e:
    print(f"Caught expected error: {e}")
