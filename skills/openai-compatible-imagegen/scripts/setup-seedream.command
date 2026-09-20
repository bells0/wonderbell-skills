#!/bin/zsh

set -u

script_dir="${0:A:h}"

if [[ -t 1 ]]; then
  clear
fi
print "火山 Seedream 一键配置"
print ""
print "接下来只需要粘贴一次 API Key。"
print "粘贴时屏幕不会显示字符，这是正常的。"
print ""

if ! command -v python3 >/dev/null 2>&1; then
  print "没有找到 Python 3。请让你的 AI 助手帮你完成配置。"
  exit_code=1
else
  python3 "$script_dir/configure.py" ark "$@"
  exit_code=$?
fi

print ""
if (( exit_code == 0 )); then
  print "现在可以关闭这个窗口，然后直接告诉你的 AI 助手想生成什么图片。"
else
  print "配置没有完成。请把上面的错误提示发给你的 AI 助手。"
fi
print "按回车键关闭窗口。"
read -r
exit $exit_code
