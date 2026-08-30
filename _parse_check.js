const fs = require('fs');
const src = fs.readFileSync('web_pet/minigame_setsuna.js', 'utf8');
const lines = src.split('\n');
// 全体パース
try {
  new Function(src);
  console.log('PARSE_OK');
} catch (e) {
  console.log('FULL_ERR:', e.message);
}
// 先頭から行を増やして初めて失敗する行を探す
const vm = require('vm');
const fs6 = require('fs');
const src6 = fs6.readFileSync('web_pet/minigame_setsuna.js', 'utf8');
try {
  new vm.Script(src6);
  console.log('PARSE_OK');
} catch (e) {
  console.log('FULL_ERR:', e.message);
  // 行単位の正しい二分探査 (vm.Script はラッパーなしでパースする)
  const ls3 = src6.replace(/\r/g, '').split('\n');
  let lo = 1;
  let hi = ls3.length;
  let firstBadLine = -1;
  for (let n = 1; n <= ls3.length; n++) {
    let msg = '';
    try {
      new vm.Script(ls3.slice(0, n).join('\n'));
    } catch (e2) {
      msg = e2.message;
    }
    // 未完了 (Unexpected end of input) は正常な途中状態、
    // それ以外の SyntaxError が出た最初の行が犯人
    if (firstBadLine < 0 && msg && !/end of input/i.test(msg)) {
      firstBadLine = n;
      console.log('FIRST_BAD at line', n, '=>', msg, '|', JSON.stringify(ls3[n - 1].slice(0, 70)));
    }
  }
}
console.log('DONE');
