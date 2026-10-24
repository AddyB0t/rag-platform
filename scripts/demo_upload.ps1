# Demo: admin uploads a finance-only document, then finance and employee ask about it.
# Requires the API running on port 8000.
$f = Join-Path $env:TEMP "board_memo.md"
Set-Content $f "# Q3 Board Memo`nNorthwind Analytics will open a new data centre in Pune in March 2027 with a budget of INR 42 crore.`n# Hiring`nThe finance team will add 6 analysts in Q4."
curl.exe -s -H "Authorization: Bearer admin-token" -F "file=@$f" -F "allowed_roles=finance" -F "title=Q3 Board Memo" http://127.0.0.1:8000/admin/upload
""
$body = @{ question = "What is the budget for the new Pune data centre?" } | ConvertTo-Json
foreach ($t in "finance-token", "employee-token") {
    $r = Invoke-RestMethod http://127.0.0.1:8000/chat -Method Post -ContentType "application/json" -Headers @{ Authorization = "Bearer $t" } -Body $body
    "$t -> $($r.answer)"
}
