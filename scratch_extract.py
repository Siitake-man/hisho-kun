html = open('web_pet/hd2d_showcase.html', encoding='utf-8').read()
script = html.split('<script id="data-script">')[1].split('</script>')[0]
open('scratch_test.js', 'w', encoding='utf-8').write(script)
print("Saved scratch_test.js successfully")
