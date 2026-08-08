$files = @(
  "C:\Users\Administrator\Desktop\笔记报告_fixed\笔记报告\小红书笔记报告\小红书矩阵笔记分析报告模版.html",
  "C:\Users\Administrator\Desktop\笔记报告_fixed\笔记报告\小红书笔记报告\小红书 - mono渠道笔记数据\小红书矩阵笔记分析报告_2026年4月.html",
  "C:\Users\Administrator\Desktop\笔记报告_fixed\笔记报告\小红书笔记报告\小红书 - on line渠道笔记数据\小红书矩阵笔记分析报告_第21周.html",
  "C:\Users\Administrator\Desktop\笔记报告_fixed\笔记报告\抖音笔记报告\抖音矩阵作品分析报告模版_2026年4月.html"
)

foreach ($f in $files) {
  $name = Split-Path $f -Leaf
  $content = Get-Content $f -Encoding UTF8 -Raw
  $size = [math]::Round($content.Length / 1024)
  $title = if ($content -match '<title>(.*?)</title>') { $matches[1] } else { "N/A" }
  $sections = [regex]::Matches($content, '<h[23][^>]*>([^<]+)') | ForEach-Object { $_.Groups[1].Value.Trim() } | Where-Object { $_ -match '维度|指南|分析|表现|健康|爆款|用户|行动' } | Select-Object -First 8
  $hasData = if ($content -match '[1-9]\d{3,}') { "有真实数据" } else { "空模板/占位符" }
  $color = if ($content -match 'fe2c55') { "抖音双色(红+青)" } elseif ($content -match 'ff2442') { "小红书红" } else { "其他" }
  $chartTypes = [regex]::Matches($content, "type:\s*'(\w+)'") | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique

  Write-Host "=== $name ==="
  Write-Host "大小: ${size}KB  主色: $color  数据状态: $hasData"
  Write-Host "标题: $title"
  Write-Host "图表类型: $($chartTypes -join ', ')"
  Write-Host "主要章节: $($sections -join ' | ')"
  Write-Host ""
}
