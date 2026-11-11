import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Bot,
  Send,
  Sparkles,
  ShieldAlert,
  FileText,
  AlertTriangle,
  RotateCcw,
  CheckCircle,
  HelpCircle,
  FileCheck2,
} from "lucide-react";
import { api } from "../api/client";
import { useCaseContext } from "../context/CaseContext";
import { CitationCard } from "../components/assistant/CitationCard";
import { EpistemicBreakdown } from "../components/assistant/EpistemicBreakdown";
import type {
  AssistantQueryRequest,
  AssistantQueryResponse,
  AssistantContextSummary,
  AssistantQuestionCategory,
  AssistantMessage,
} from "../types/api";

interface ChatTurn {
  id: string;
  question: string;
  categoryHint?: AssistantQuestionCategory;
  response?: AssistantQueryResponse;
  isLoading?: boolean;
  error?: string;
}

const CATEGORY_PROMPTS: {
  category: AssistantQuestionCategory;
  label: string;
  prompt: string;
  icon: React.ReactNode;
}[] = [
  {
    category: "INVESTIGATION_SUMMARY",
    label: "Case Summary",
    prompt: "Provide an investigation summary of all documents, findings, and review determinations in this case.",
    icon: <FileCheck2 className="w-3.5 h-3.5 text-emerald-400" />,
  },
  {
    category: "CONTRADICTION_ANALYSIS",
    label: "Contradiction Check",
    prompt: "Identify any contradictory evidence or numerical discrepancies detected across case documents.",
    icon: <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />,
  },
  {
    category: "CROSS_DOCUMENT_COMPARISON",
    label: "Compare Documents",
    prompt: "Compare extracted monetary totals and vendor details across the documents in this case.",
    icon: <FileText className="w-3.5 h-3.5 text-cyan-400" />,
  },
  {
    category: "EVIDENCE_EXPLANATION",
    label: "Explain Findings",
    prompt: "Explain the active forensic findings in this case and which specific source records support them.",
    icon: <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />,
  },
  {
    category: "ENTITY_INVESTIGATION",
    label: "Investigate Entities",
    prompt: "Summarize the extracted entities and candidate matches without merging unconfirmed identities.",
    icon: <Sparkles className="w-3.5 h-3.5 text-indigo-400" />,
  },
  {
    category: "FOLLOW_UP_SUGGESTIONS",
    label: "Suggest Next Steps",
    prompt: "Suggest evidence-grounded follow-up investigative questions based on the unresolved findings.",
    icon: <HelpCircle className="w-3.5 h-3.5 text-slate-300" />,
  },
];

export const AssistantPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const { activeCase } = useCaseContext();
  const [question, setQuestion] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<AssistantQuestionCategory | undefined>(undefined);
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  // 1. Fetch case context summary
  const { data: summary } = useQuery<AssistantContextSummary>({
    queryKey: ["assistant-context-summary", caseId],
    queryFn: () => api.get<AssistantContextSummary>(`/cases/${caseId}/assistant/context-summary`),
    enabled: !!caseId,
  });

  // 2. Query mutation
  const queryMutation = useMutation<AssistantQueryResponse, Error, AssistantQueryRequest>({
    mutationFn: (req) => api.post<AssistantQueryResponse>(`/cases/${caseId}/assistant/query`, req),
  });

  const handleSend = async (qToSend?: string, catHint?: AssistantQuestionCategory) => {
    const queryText = (qToSend || question).trim();
    if (!queryText || !caseId || queryMutation.isPending) return;

    const turnId = `turn-${Date.now()}`;
    const newTurn: ChatTurn = {
      id: turnId,
      question: queryText,
      categoryHint: catHint || selectedCategory,
      isLoading: true,
    };

    setTurns((prev) => [...prev, newTurn]);
    setQuestion("");

    // Assemble conversation context
    const conversationContext: AssistantMessage[] = [];
    turns.forEach((t) => {
      conversationContext.push({ role: "user", content: t.question });
      if (t.response) {
        conversationContext.push({ role: "assistant", content: t.response.answer_text });
      }
    });

    try {
      const resp = await queryMutation.mutateAsync({
        question: queryText,
        category_hint: catHint || selectedCategory,
        conversation_context: conversationContext,
        reviewer_id: "lead-investigator",
      });

      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, isLoading: false, response: resp } : t))
      );
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to query assistant.";
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, isLoading: false, error: errorMsg } : t))
      );
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearSession = () => {
    setTurns([]);
    setQuestion("");
    setSelectedCategory(undefined);
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-evidexa-slate/80">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-1">
            <Link to="/cases" className="hover:text-evidexa-cyan">Cases</Link>
            <span>/</span>
            <Link to={`/cases/${caseId}/overview`} className="hover:text-evidexa-cyan font-bold text-slate-300">
              {activeCase?.case_reference || caseId?.slice(0, 8)}
            </Link>
            <span>/</span>
            <span className="text-evidexa-cyan font-semibold">Grounded AI Assistant</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            <Bot className="w-6 h-6 text-evidexa-cyan" />
            <span>Grounded Investigation Assistant</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Authoritative, evidence-grounded AI assistant with strict epistemic separation and traceable citations.
          </p>
        </div>

        {/* Evidence Status Pill */}
        {summary && (
          <div className="flex items-center gap-3 bg-evidexa-charcoal px-3 py-2 rounded-lg border border-evidexa-slate text-xs font-mono text-slate-300 shrink-0">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase">Retrievable Context</span>
              <span className="font-bold text-white">
                {summary.counts.documents} docs • {summary.counts.forensic_findings + summary.counts.consistency_findings} findings • {summary.counts.entities} entities
              </span>
            </div>
            {turns.length > 0 && (
              <button
                type="button"
                onClick={clearSession}
                className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors ml-2 border border-slate-700"
                title="Clear conversation history"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Mandatory Epistemic AI Notice Banner */}
      <div className="p-3.5 rounded-lg bg-evidexa-midnight/80 border border-evidexa-slate flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-300 leading-relaxed">
          <span className="font-semibold text-white">EVIDEXA Evidentiary AI Boundary: </span>
          This assistant synthesizes information strictly from authoritative case records. It separates observed facts from automated signals and analytical interpretations. It does{" "}
          <strong className="text-amber-300">not</strong> provide autonomous legal verdicts, accusations, or fraud conclusions.
        </div>
      </div>

      {/* Quick Task Category Chips */}
      <div>
        <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold mb-2 block">
          Investigative Task Quick Actions
        </span>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          {CATEGORY_PROMPTS.map((cp) => (
            <button
              key={cp.category}
              type="button"
              onClick={() => {
                setSelectedCategory(cp.category);
                handleSend(cp.prompt, cp.category);
              }}
              className="p-2.5 rounded-lg bg-evidexa-charcoal/80 border border-evidexa-slate hover:border-evidexa-cyan/60 transition-all text-left group flex flex-col justify-between"
            >
              <div className="flex items-center gap-1.5 mb-1">
                {cp.icon}
                <span className="text-xs font-semibold text-slate-200 group-hover:text-evidexa-cyan transition-colors truncate">
                  {cp.label}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 line-clamp-2">
                {cp.prompt}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Conversation Thread */}
      <div className="space-y-6">
        {turns.length === 0 ? (
          <div className="p-8 text-center rounded-xl bg-evidexa-charcoal/40 border border-dashed border-evidexa-slate/80">
            <Bot className="w-10 h-10 text-slate-500 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-200 mb-1">No Active Queries</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto mb-4">
              Ask any question about documents, findings, numerical comparisons, or entity relationships in this case. Every factual answer carries verifiable evidence citations.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <button
                type="button"
                onClick={() => handleSend("Provide an investigation summary of all documents, findings, and review determinations in this case.", "INVESTIGATION_SUMMARY")}
                className="px-3 py-1.5 text-xs font-mono font-medium rounded-md bg-evidexa-slate text-evidexa-cyan hover:bg-slate-700 transition-colors"
              >
                Summarize Case Evidence
              </button>
              <button
                type="button"
                onClick={() => handleSend("Identify any contradictory evidence or numerical discrepancies detected across case documents.", "CONTRADICTION_ANALYSIS")}
                className="px-3 py-1.5 text-xs font-mono font-medium rounded-md bg-evidexa-slate text-evidexa-cyan hover:bg-slate-700 transition-colors"
              >
                Inspect Contradictions
              </button>
            </div>
          </div>
        ) : (
          turns.map((turn, turnIdx) => (
            <div key={turn.id} className="space-y-4">
              {/* Investigator User Query Card */}
              <div className="flex justify-end">
                <div className="max-w-2xl bg-evidexa-slate/90 border border-slate-700 rounded-xl p-4 text-slate-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-1 text-[11px] font-mono text-evidexa-cyan font-semibold">
                    <span>Investigator Query #{turnIdx + 1}</span>
                    {turn.categoryHint && (
                      <span className="px-1.5 py-0.2 rounded bg-slate-800 text-[10px] text-slate-300">
                        {turn.categoryHint}
                      </span>
                    )}
                  </div>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{turn.question}</p>
                </div>
              </div>

              {/* Assistant Grounded Response Card */}
              <div className="flex justify-start">
                <div className="max-w-4xl w-full bg-evidexa-charcoal border border-evidexa-slate rounded-xl p-5 shadow-lg space-y-4">
                  {/* Response Header */}
                  <div className="flex items-center justify-between pb-3 border-b border-evidexa-slate/70">
                    <div className="flex items-center gap-2.5">
                      <div className="p-1.5 rounded-md bg-evidexa-midnight border border-evidexa-slate text-evidexa-cyan">
                        <Bot className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-white block">EVIDEXA Grounded Assistant</span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {turn.response ? `${turn.response.model_name} • ${turn.response.question_category}` : "Processing..."}
                        </span>
                      </div>
                    </div>

                    {turn.response && (
                      <div className="flex items-center gap-1.5">
                        {!turn.response.has_sufficient_evidence ? (
                          <span
                            title="Case evidence is insufficient to fully substantiate answers without speculation."
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800 flex items-center gap-1"
                          >
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            Insufficient Evidence
                          </span>
                        ) : turn.response.citations.length > 0 ? (
                          <span
                            title="Citations resolve to case evidence records. Lexical relevance confirmed; semantic verification requires investigator review."
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700 flex items-center gap-1"
                          >
                            <CheckCircle className="w-3 h-3 text-cyan-400" />
                            Citations Linked ({turn.response.citations.length})
                          </span>
                        ) : (
                          <span
                            title="No direct documentary citations were returned for this inquiry."
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800 flex items-center gap-1"
                          >
                            General Summary (No Direct Citations)
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Loading State */}
                  {turn.isLoading && (
                    <div className="p-6 text-center space-y-2">
                      <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-evidexa-cyan border-t-transparent" />
                      <p className="text-xs font-mono text-slate-400">
                        Retrieving case records & synthesizing citations…
                      </p>
                    </div>
                  )}

                  {/* Error State */}
                  {turn.error && (
                    <div
                      data-testid="assistant-provider-error-alert"
                      role="alert"
                      className="p-4 bg-rose-950/40 border border-rose-900 rounded-lg text-xs text-rose-300 space-y-2"
                    >
                      <div className="flex items-center gap-2 font-semibold text-rose-200">
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                        <span>Assistant Provider Failure</span>
                      </div>
                      <p className="text-slate-300 leading-relaxed">{turn.error}</p>
                      <div className="pt-2 flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => handleSend(turn.question, turn.categoryHint)}
                          className="px-3 py-1.5 rounded-md bg-rose-900/60 hover:bg-rose-900 text-rose-200 font-mono text-[11px] font-medium transition-colors"
                        >
                          Retry Query
                        </button>
                        <span className="text-[11px] text-slate-400 font-mono">
                          Check backend LLM provider connectivity or retry after a moment.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Grounded Response Content */}
                  {turn.response && (
                    <>
                      {/* Insufficient Evidence Warning Banner */}
                      {!turn.response.has_sufficient_evidence && (
                        <div className="p-3 bg-amber-950/40 border border-amber-900 rounded-lg text-xs text-amber-300 flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold block">Insufficient Case Evidence Notice</span>
                            The available case records are insufficient to fully answer this query without speculation.
                          </div>
                        </div>
                      )}

                      {/* Main Answer Narrative */}
                      <div className="text-sm text-slate-100 leading-relaxed space-y-2 whitespace-pre-wrap">
                        {turn.response.answer_text}
                      </div>

                      {/* Evidence Citations Section */}
                      {turn.response.citations.length > 0 && (
                        <div className="pt-2">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider">
                              Verifiable Citations ({turn.response.citations.length})
                            </span>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                            {turn.response.citations.map((cite) => (
                              <CitationCard key={cite.citation_id} citation={cite} />
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Epistemic Evidence Breakdown */}
                      <EpistemicBreakdown
                        observedFacts={turn.response.observed_facts}
                        automatedIndicators={turn.response.automated_indicators}
                        analyticalInterpretations={turn.response.analytical_interpretations}
                        contradictoryEvidence={turn.response.contradictory_evidence}
                        unresolvedQuestions={turn.response.unresolved_questions}
                        limitations={turn.response.limitations}
                      />

                      {/* Follow-up Suggestions Chips */}
                      {turn.response.follow_up_suggestions.length > 0 && (
                        <div className="pt-3 border-t border-evidexa-slate/60">
                          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider font-semibold block mb-2">
                            Suggested Follow-Up Queries
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {turn.response.follow_up_suggestions.map((sug, i) => (
                              <button
                                key={i}
                                type="button"
                                onClick={() => handleSend(sug)}
                                className="px-2.5 py-1 text-xs font-medium rounded-full bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors text-left flex items-center gap-1.5"
                              >
                                <Sparkles className="w-3 h-3 text-evidexa-cyan" />
                                <span>{sug}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Question Input Console */}
      <div className="sticky bottom-4 bg-evidexa-midnight/95 backdrop-blur-md p-4 rounded-xl border border-evidexa-slate/90 shadow-2xl space-y-2">
        <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
          <span>Ask investigator question (Enter to send, Shift+Enter for newline)</span>
          {activeCase?.status === "ARCHIVED" && (
            <span className="text-amber-400 font-semibold">
              Archived Case (Read-Only Querying)
            </span>
          )}
        </div>

        <div className="flex gap-2">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. Compare the invoice gross amount against the receipt payment records, or explain structural findings..."
            rows={2}
            className="flex-1 bg-evidexa-charcoal border border-evidexa-slate rounded-lg p-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-evidexa-cyan focus:border-transparent resize-none"
          />

          <button
            type="button"
            onClick={() => handleSend()}
            disabled={!question.trim() || queryMutation.isPending}
            className="px-5 py-3 rounded-lg bg-evidexa-cyan hover:bg-evidexa-cyan/90 text-slate-950 font-bold text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all shrink-0 self-end"
          >
            {queryMutation.isPending ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-slate-950 border-t-transparent" />
                <span>Thinking…</span>
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span>Send</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

