export function ProjectDetailSkeleton() {
  return (
    <div className="min-h-screen bg-background text-foreground animate-pulse">
      {/* Header Skeleton */}
      <header className="border-b border-border bg-card/20">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="h-4 w-24 bg-muted rounded" />
        </div>
      </header>

      {/* Main Content Skeleton */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column Skeleton (Project Info) */}
          <div className="lg:col-span-2">
            <div className="bg-card/50 rounded-2xl border border-border p-8 h-full">
              {/* Title & Description */}
              <div className="mb-8 space-y-4">
                <div className="h-8 w-3/4 bg-muted rounded" />
                <div className="h-5 w-1/2 bg-muted rounded" />
              </div>

              {/* Metadata Rows */}
              <div className="space-y-6 mb-8">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="h-5 w-5 rounded bg-muted" />
                    <div className="h-4 w-32 bg-muted rounded" />
                  </div>
                ))}
              </div>

              {/* Button Skeleton */}
              <div className="h-12 w-40 bg-muted rounded-xl" />
            </div>
          </div>

          {/* Right Column Skeleton (Production Pipeline) */}
          <div className="lg:col-span-1">
            <div className="bg-card/50 rounded-2xl border border-border p-6 h-full">
              <div className="h-5 w-24 bg-muted rounded mb-6" />
              
              <div className="space-y-5">
                {[1, 2, 3, 4, 5, 6, 7].map((i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="h-4 w-4 rounded-full bg-muted" />
                    <div className="h-4 w-20 bg-muted rounded" />
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}