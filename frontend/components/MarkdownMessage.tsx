import type { ReactNode } from "react"

function normalizeMarkdown(value: string) {
  return value
    .replace(/\r\n?/g, "\n")
    .replace(/\\\n/g, "\n")
    .replace(/&#x20;|&#32;|&nbsp;/gi, " ")
    .replace(/&#x202f;|&#8239;|&#xa0;|&#160;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/[\u00a0\u2007\u202f]/g, " ")
    .replace(/\\([\\`*_[\]()|#:>])/g, "$1")
    .replace(/[ \t]+$/gm, "")
    .trim()
}

function renderInline(value: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /\[([^\]]+)]\((https?:\/\/[^)\s]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*/g
  let cursor = 0
  let match: RegExpExecArray | null

  while ((match = pattern.exec(value)) !== null) {
    if (match.index > cursor) nodes.push(value.slice(cursor, match.index))

    const key = `${keyPrefix}-${match.index}`
    if (match[1] && match[2]) {
      nodes.push(
        <a href={match[2]} key={key} rel="noreferrer noopener" target="_blank">
          {match[1]}
        </a>
      )
    } else if (match[3]) {
      nodes.push(<strong key={key}>{match[3]}</strong>)
    } else if (match[4]) {
      nodes.push(<code key={key}>{match[4]}</code>)
    } else if (match[5]) {
      nodes.push(<em key={key}>{match[5]}</em>)
    }

    cursor = pattern.lastIndex
  }

  if (cursor < value.length) nodes.push(value.slice(cursor))
  return nodes
}

function isTableSeparator(value: string) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(value)
}

function tableCells(value: string) {
  return value
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => cell.trim())
}

function isBlockStart(lines: string[], index: number) {
  const line = lines[index]
  return (
    /^#{1,3}\s+/.test(line) ||
    /^[-*]\s+/.test(line) ||
    /^\d+\.\s+/.test(line) ||
    /^```/.test(line) ||
    (line.includes("|") && isTableSeparator(lines[index + 1] || ""))
  )
}

export function MarkdownMessage({ children }: { children: string }) {
  const lines = normalizeMarkdown(children).split("\n")
  const blocks: ReactNode[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) {
      index += 1
      continue
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      const content = renderInline(heading[2], `heading-${index}`)
      blocks.push(
        heading[1].length === 1
          ? <h2 key={`heading-${index}`}>{content}</h2>
          : <h3 key={`heading-${index}`}>{content}</h3>
      )
      index += 1
      continue
    }

    if (line.startsWith("```")) {
      const codeLines: string[] = []
      index += 1
      while (index < lines.length && !lines[index].startsWith("```")) {
        codeLines.push(lines[index])
        index += 1
      }
      if (index < lines.length) index += 1
      blocks.push(
        <pre key={`code-${index}`}>
          <code>{codeLines.join("\n")}</code>
        </pre>
      )
      continue
    }

    if (line.includes("|") && isTableSeparator(lines[index + 1] || "")) {
      const headers = tableCells(line)
      const rows: string[][] = []
      index += 2
      while (index < lines.length && lines[index].includes("|")) {
        rows.push(tableCells(lines[index]))
        index += 1
      }
      blocks.push(
        <div className="markdownTableWrap" key={`table-${index}`}>
          <table>
            <thead>
              <tr>
                {headers.map((header, cellIndex) => (
                  <th key={`header-${cellIndex}`}>
                    {renderInline(header, `header-${cellIndex}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`row-${rowIndex}`}>
                  {headers.map((_, cellIndex) => (
                    <td key={`cell-${rowIndex}-${cellIndex}`}>
                      {renderInline(row[cellIndex] || "", `cell-${rowIndex}-${cellIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = []
      while (index < lines.length) {
        if (!/^[-*]\s+/.test(lines[index])) break

        let item = lines[index].replace(/^[-*]\s+/, "")
        index += 1

        while (index < lines.length && /^\s{2,}\S/.test(lines[index])) {
          item += ` ${lines[index].trim()}`
          index += 1
        }

        items.push(item)

        const nextContent = lines.slice(index).findIndex((candidate) => candidate.trim())
        if (nextContent < 0) {
          index = lines.length
          break
        }

        const nextIndex = index + nextContent
        if (!/^[-*]\s+/.test(lines[nextIndex])) break
        index = nextIndex
      }
      blocks.push(
        <ul key={`list-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`item-${itemIndex}`}>
              {renderInline(item, `item-${itemIndex}`)}
            </li>
          ))}
        </ul>
      )
      continue
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = []
      while (index < lines.length) {
        if (!/^\d+\.\s+/.test(lines[index])) break

        let item = lines[index].replace(/^\d+\.\s+/, "")
        index += 1

        while (index < lines.length && /^\s{2,}\S/.test(lines[index])) {
          item += ` ${lines[index].trim()}`
          index += 1
        }

        items.push(item)

        const nextContent = lines.slice(index).findIndex((candidate) => candidate.trim())
        if (nextContent < 0) {
          index = lines.length
          break
        }

        const nextIndex = index + nextContent
        if (!/^\d+\.\s+/.test(lines[nextIndex])) break
        index = nextIndex
      }
      blocks.push(
        <ol key={`ordered-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`ordered-item-${itemIndex}`}>
              {renderInline(item, `ordered-item-${itemIndex}`)}
            </li>
          ))}
        </ol>
      )
      continue
    }

    const paragraphLines = [line]
    index += 1
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines, index)) {
      paragraphLines.push(lines[index])
      index += 1
    }
    blocks.push(
      <p key={`paragraph-${index}`}>
        {renderInline(paragraphLines.join(" "), `paragraph-${index}`)}
      </p>
    )
  }

  return <div className="messageMarkdown">{blocks}</div>
}
