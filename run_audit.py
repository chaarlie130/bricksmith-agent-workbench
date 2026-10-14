from bricknet.engine import check_model
result = check_model("the_reichstag.ldr")
print("Audit Result:", "PASS ✓" if result['pass'] else "FAIL ✗")
for k, v in result.items():
    if k != 'pass':
        print(f"  {'✓' if v else '✗'} {k}: {v}")
