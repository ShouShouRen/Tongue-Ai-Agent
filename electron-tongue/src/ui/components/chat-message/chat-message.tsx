import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface Message {
  user: 'user' | 'assistant' | 'me' | 'gpt';
  message: string;
  imageUrl?: string;
  toolStatus?: string;
}

interface ChatMessageProps {
  message: Message;
}

const ChatMessage = ({ message }: ChatMessageProps) => {
  const isUser = message.user === 'user' || message.user === 'me';
  const isAssistant = message.user === 'assistant' || message.user === 'gpt';

  return (
    <div className={`flex w-full max-w-[1200px] mx-auto ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex gap-3 max-w-[75%] items-start ${isUser ? 'flex-row-reverse' : ''} md:max-w-[75%]`}>
        <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center border ${isUser ? 'bg-mit-red text-white border-mit-red' : 'bg-gray-100 text-gray-600 border-gray-200'} md:w-8 md:h-8`}>
          {isAssistant && (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="md:w-[18px] md:h-[18px]"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          )}
          {isUser && (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="md:w-[18px] md:h-[18px]"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          )}
        </div>

        <div className={`py-3 px-4 rounded-xl text-sm leading-relaxed break-words max-w-full ${
          isUser 
            ? 'bg-mit-red text-white rounded-br-sm whitespace-pre-wrap' 
            : 'bg-white text-gray-800 border border-gray-200 rounded-bl-sm shadow-sm'
        } md:py-3 md:px-4 md:text-sm`}>
          {message.imageUrl && (
            <img 
              src={message.imageUrl} 
              alt="上傳的圖片"
              className="max-w-full max-h-[400px] rounded-lg mt-2 mb-0 object-contain block shadow-md first:mt-0"
            />
          )}
          {message.toolStatus && isAssistant && (
            <div className="mb-2 pb-2 border-b border-gray-200">
              <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-2 py-1.5 rounded-md border border-blue-200">
                <svg 
                  width="14" 
                  height="14" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="animate-tool-spin shrink-0"
                >
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                <span className="font-medium">{message.toolStatus}</span>
              </div>
            </div>
          )}
          {message.message ? (
            isAssistant ? (
              <div className="markdown-content prose prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={{
                    h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-2 first:mt-0 text-gray-800" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-4 mb-2 first:mt-0 text-gray-800" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-base font-bold mt-3 mb-2 first:mt-0 text-gray-800" {...props} />,
                    h4: ({node, ...props}) => <h4 className="text-sm font-bold mt-2 mb-1 first:mt-0 text-gray-800" {...props} />,
                    p: ({node, ...props}) => <p className="mb-2 last:mb-0 text-gray-800" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc mb-2 space-y-1.5 ml-4 text-gray-800" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal mb-2 space-y-1.5 ml-4 text-gray-800" {...props} />,
                    li: ({node, ...props}) => <li className="text-gray-800 leading-relaxed" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold text-gray-900" {...props} />,
                    em: ({node, ...props}) => <em className="italic" {...props} />,
                    hr: ({node, ...props}) => <hr className="my-4 border-gray-300" {...props} />,
                    code: ({node, inline, ...props}: any) => 
                      inline ? (
                        <code className="bg-gray-100 px-1 py-0.5 rounded text-xs font-mono text-gray-800" {...props} />
                      ) : (
                        <code className="block bg-gray-100 p-2 rounded text-xs font-mono overflow-x-auto mb-2 text-gray-800" {...props} />
                      ),
                    blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2 text-gray-700" {...props} />,
                  }}
                >
                  {message.message}
                </ReactMarkdown>
              </div>
            ) : (
              <div>{message.message}</div>
            )
          ) : isAssistant ? (
            <div className="flex items-center gap-2 py-1">
              <span className="text-gray-500 text-sm">正在思考</span>
              <div className="flex gap-1.5 items-center">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-thinking" style={{ animationDelay: '0ms' }}></span>
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-thinking" style={{ animationDelay: '200ms' }}></span>
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-thinking" style={{ animationDelay: '400ms' }}></span>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default ChatMessage