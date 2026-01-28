import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { HttpClient, HttpErrorResponse } from "@angular/common/http";
import { Router } from "@angular/router";
import { environment } from "../environments/environment";

type IngestionResponse = {
  company_id: string;
  company_name: string;
  ticker: string;
  transcript_id: string;
  fiscal_year: number;
  fiscal_quarter: number;
};

type TranscriptHit = {
  transcript_id: string;
  company_id: string;
  fiscal_year?: number | null;
  fiscal_quarter?: number | null;
  rank: number;
  snippet: string;
};

type TranscriptSummary = {
  transcript_id: string;
  fiscal_year: number;
  fiscal_quarter: number;
};

type ListTranscriptResponse = {
  company_id: string;
  company_name: string;
  company_transcripts: TranscriptSummary[];
};

type QueryResponse = {
  total: number;
  hits: TranscriptHit[];
};

type RagSource = {
  company_id: string;
  transcript_id: string;
  chunk_id: string;
  speaker?: string | null;
  paragraph_num?: number | null;
  score: number;
  snippet: string;
};

type RagResponse = {
  answer: string;
  sources: RagSource[];
};

type SearchPayload = {
  query: string;
  limit: number;
  offset: number;
  company_id?: string;
  fiscal_year?: number;
  fiscal_quarter?: number;
};

type QnaCompanyPayload = {
  company_name_query: string;
  security_type: string;
  exchange_code: string;
  year?: number;
  quarter?: number;
};

type QnaPayload = {
  question: string;
  company: QnaCompanyPayload;
};

@Component({
  selector: "app-home",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./home.component.html",
  styleUrls: ["./home.component.css"]
})
export class HomeComponent {
  apiBaseUrl = environment.apiBaseUrl;
  snippetDelimiter = " \u0192?\u0130 ";

  ingest = {
    company_name_query: "",
    security_type: "Common Stock",
    exchange_code: "US",
    year: new Date().getFullYear(),
    quarter: 1
  };
  ingestLoading = false;
  ingestError = "";
  ingestResult: IngestionResponse | null = null;

  listTranscripts = {
    company_name_query: "",
    security_type: "Common Stock",
    exchange_code: "US"
  };
  listLoading = false;
  listError = "";
  listResult: ListTranscriptResponse | null = null;

  search = {
    query: "",
    company_id: "",
    fiscal_year: "",
    fiscal_quarter: "",
    limit: 20,
    offset: 0
  };
  searchLoading = false;
  searchError = "";
  searchResult: QueryResponse | null = null;

  qna = {
    question: ""
  };
  qnaCompany = {
    company_name_query: "",
    security_type: "Common Stock",
    exchange_code: "US",
    year: "",
    quarter: ""
  };
  qnaLoading = false;
  qnaError = "";
  qnaResult: RagResponse | null = null;

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  runIngest(): void {
    this.ingestError = "";
    this.ingestResult = null;
    const trimmedCompany = this.ingest.company_name_query.trim();
    if (!trimmedCompany) {
      this.ingestError = "Company name is required.";
      return;
    }
    const payload = {
      company_name_query: trimmedCompany,
      security_type: this.ingest.security_type.trim() || "Common Stock",
      exchange_code: this.ingest.exchange_code.trim() || "US",
      year: Number(this.ingest.year),
      quarter: Number(this.ingest.quarter)
    };
    this.ingestLoading = true;
    this.http.post<IngestionResponse>(this.apiUrl("/ingest/ingest-in"), payload).subscribe({
      next: (res) => {
        this.ingestResult = res;
        this.ingestLoading = false;
      },
      error: (err) => {
        this.ingestError = this.readError(err);
        this.ingestLoading = false;
      }
    });
  }

  runListTranscripts(): void {
    this.listError = "";
    this.listResult = null;

    const trimmedCompany = this.listTranscripts.company_name_query.trim();
    if (!trimmedCompany) {
      this.listError = "Company name is required.";
      return;
    }

    // const payload = {
    //   company_name_query: trimmedCompany,
    //   // security_type: this.listTranscripts.security_type.trim() || "Common Stock",
    //   // exchange_code: this.listTranscripts.exchange_code.trim() || "US",
    //   // year: new Date().getFullYear(), // unused but required by backend schema
    //   // quarter: 1
    // };

    this.listLoading = true;

    this.http.request<ListTranscriptResponse>(
      "GET",
      this.apiUrl(`/ingest/ingest-out/${trimmedCompany}`)
    ).subscribe({
      next: (res) => {
        this.listResult = res;
        this.listLoading = false;
      },
      error: (err) => {
        this.listError = this.readError(err);
        this.listLoading = false;
      }
    });
  }

  openTranscript(transcriptId: string): void {
    if (!transcriptId) {
      return;
    }
    this.router.navigate(["/transcripts", transcriptId]);
  }

  runSearch(): void {
    this.searchError = "";
    this.searchResult = null;
    const trimmedQuery = this.search.query.trim();
    if (!trimmedQuery) {
      this.searchError = "Search query is required.";
      return;
    }
    const payload: SearchPayload = {
      query: trimmedQuery,
      limit: this.toNumber(this.search.limit) ?? 20,
      offset: this.toNumber(this.search.offset) ?? 0
    };
    const companyId = this.search.company_id.trim();
    if (companyId) {
      payload.company_id = companyId;
    }
    const fiscalYear = this.toNumber(this.search.fiscal_year);
    if (fiscalYear !== null) {
      payload.fiscal_year = fiscalYear;
    }
    const fiscalQuarter = this.toNumber(this.search.fiscal_quarter);
    if (fiscalQuarter !== null) {
      payload.fiscal_quarter = fiscalQuarter;
    }
    this.searchLoading = true;
    this.http.post<QueryResponse>(this.apiUrl("/search/query"), payload).subscribe({
      next: (res) => {
        this.searchResult = res;
        this.searchLoading = false;
      },
      error: (err) => {
        this.searchError = this.readError(err);
        this.searchLoading = false;
      }
    });
  }

  runQna(): void {
    this.qnaError = "";
    this.qnaResult = null;
    const trimmedQuestion = this.qna.question.trim();
    if (!trimmedQuestion) {
      this.qnaError = "Question is required.";
      return;
    }
    const payload: QnaPayload = {
      question: trimmedQuestion,
      company: {
        company_name_query: "",
        security_type: "Common Stock",
        exchange_code: "US"
      }
    };
    const name = this.qnaCompany.company_name_query.trim();
    if (!name) {
      this.qnaError = "Company name is required for Q&A in the current backend.";
      return;
    }
    const companyPayload: QnaCompanyPayload = {
      company_name_query: name,
      security_type: this.qnaCompany.security_type.trim() || "Common Stock",
      exchange_code: this.qnaCompany.exchange_code.trim() || "US"
    };
    const year = this.toNumber(this.qnaCompany.year);
    if (year !== null) {
      companyPayload.year = year;
    }
    const quarter = this.toNumber(this.qnaCompany.quarter);
    if (quarter !== null) {
      companyPayload.quarter = quarter;
    }
    payload.company = companyPayload;
    this.qnaLoading = true;
    this.http.post<RagResponse>(this.apiUrl("/qna/ask"), payload).subscribe({
      next: (res) => {
        this.qnaResult = res;
        this.qnaLoading = false;
      },
      error: (err) => {
        this.qnaError = this.readError(err);
        this.qnaLoading = false;
      }
    });
  }

  formatAnswer(answer: string): string {
    if (!answer) {
      return "";
    }
    const citationRegex = /\[chunk_id=([0-9a-fA-F-]+)([^\]]*)\]/g;
    let result = "";
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = citationRegex.exec(answer)) !== null) {
      result += this.escapeHtml(answer.slice(lastIndex, match.index));
      const chunkId = match[1] ?? "";
      const rest = match[2] ?? "";
      const short = chunkId.slice(0, 5);
      const speakerMatch = /chunk_speaker=([^,\]]+)/.exec(rest);
      const paraMatch = /para_number=([^,\]]+)/.exec(rest);
      const titleParts = [`chunk_id=${chunkId}`];
      if (speakerMatch?.[1]) {
        titleParts.push(`speaker=${speakerMatch[1].trim()}`);
      }
      if (paraMatch?.[1]) {
        titleParts.push(`para=${paraMatch[1].trim()}`);
      }
      const title = this.escapeHtml(titleParts.join(" â€¢ "));
      result += `<span class="citation" title="${title}">[${this.escapeHtml(short)}]</span>`;
      lastIndex = match.index + match[0].length;
    }

    result += this.escapeHtml(answer.slice(lastIndex));
    return result.replace(/\n/g, "<br>");
  }

  shortId(value: string | null | undefined, length = 5): string {
    if (!value) {
      return "";
    }
    return value.slice(0, length);
  }

  snippetFragments(snippet: string): string[] {
    return snippet
      .split(this.snippetDelimiter)
      .map((fragment) => fragment.trim())
      .filter((fragment) => fragment.length > 0);
  }

  private apiUrl(path: string): string {
    const base = this.apiBaseUrl.replace(/\/+$/, "");
    return `${base}${path}`;
  }

  private toNumber(value: string | number | null | undefined): number | null {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value === "number") {
      return Number.isFinite(value) ? value : null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  private readError(err: HttpErrorResponse): string {
    if (err.error) {
      const detail = (err.error as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        const joined = detail
          .map((entry) => {
            if (typeof entry === "string") {
              return entry;
            }
            if (entry && typeof entry === "object" && "msg" in entry) {
              return String((entry as { msg?: unknown }).msg);
            }
            return JSON.stringify(entry);
          })
          .join(" | ");
        if (joined) {
          return joined;
        }
      }
      if (typeof err.error === "string") {
        return err.error;
      }
    }
    return err.message || "Request failed.";
  }

  private escapeHtml(value: string): string {
    return value.replace(/[&<>"']/g, (char) => {
      switch (char) {
        case "&":
          return "&amp;";
        case "<":
          return "&lt;";
        case ">":
          return "&gt;";
        case "\"":
          return "&quot;";
        case "'":
          return "&#39;";
        default:
          return char;
      }
    });
  }
}
