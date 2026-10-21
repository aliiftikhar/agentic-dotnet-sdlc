using System.Reflection;
using System.Text.RegularExpressions;
using MediatR;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using NetArchTest.Rules;

namespace <UnitTestNamespace>.Architecture;

// Architecture rules from AGENTS.md as tests that run on every test run (locally and in CI).
// Assumes a MediatR use-case layout: <RootNamespace>.UseCases.<UseCase> with one handler per use case,
// and minimal-API endpoints mapped on `app` in Program.cs.
// Needs packages in the test project: NUnit, NetArchTest.Rules, Microsoft.CodeAnalysis.CSharp.
// Don't add entries to the allow-lists without the repo owner's approval.
[TestFixture]
public class ArchitectureTests
{
    // --- Configure for your repository ---------------------------------------------
    private const string SolutionFile = "<Solution>.sln";
    private const string ApiProjectFolder = "<ApiProject>";
    private const string UseCasesNamespace = "<RootNamespace>.UseCases";
    private static readonly Assembly ApiAssembly = typeof(<AnyPublicTypeInApiProject>).Assembly;
    // ---------------------------------------------------------------------------------

    // Approved exceptions: { use case, other use case it may import from }. Keep empty if you can.
    private static readonly HashSet<(string UseCase, string Dependency)> AllowedUseCaseDependencies = [];

    // Route-mapping calls checked for authorization (add others, e.g. MapFallback, when you use them)
    private static readonly HashSet<string> EndpointMethods = ["MapGet", "MapPost", "MapPut", "MapDelete", "MapPatch", "MapMethods"];

    // Endpoints that are deliberately public
    private static readonly HashSet<string> PublicEndpoints = [];

    [Test]
    public void UseCases_DoNotDependOnOtherUseCases()
    {
        var useCases = ApiAssembly.GetTypes()
            .Select(type => type.Namespace)
            .Where(ns => ns != null && ns.StartsWith(UseCasesNamespace + "."))
            .Select(ns => ns![(UseCasesNamespace.Length + 1)..].Split('.')[0])
            .Distinct()
            .ToList();

        var violations = new List<string>();
        var usedAllowances = new HashSet<(string, string)>();

        foreach (var useCase in useCases)
        {
            foreach (var other in useCases.Where(other => other != useCase))
            {
                // Exact type names: namespace prefixes would confuse GetThing with GetThings
                var otherTypes = TypesInUseCase(other).Select(type => type.FullName!).ToArray();
                var result = Types.InAssembly(ApiAssembly)
                    .That().ResideInNamespaceMatching($"^{Regex.Escape($"{UseCasesNamespace}.{useCase}")}(\\..*)?$")
                    .ShouldNot().HaveDependencyOnAny(otherTypes)
                    .GetResult();

                if (result.IsSuccessful)
                    continue;

                if (AllowedUseCaseDependencies.Contains((useCase, other)))
                    usedAllowances.Add((useCase, other));
                else
                    violations.Add($"{useCase} -> {other} ({string.Join(", ", result.FailingTypeNames ?? [])})");
            }
        }

        Assert.That(violations, Is.Empty,
            "Use cases must not import from other use cases. Move the shared type to a shared folder instead. Violations: "
            + string.Join("; ", violations));

        var fixedAllowances = AllowedUseCaseDependencies.Except(usedAllowances).ToList();
        Assert.That(fixedAllowances, Is.Empty,
            "These allowed dependencies no longer exist; remove them from AllowedUseCaseDependencies: "
            + string.Join(", ", fixedAllowances));
    }

    [Test]
    public void EveryHandler_HasATestClass()
    {
        var handlers = ApiAssembly.GetTypes()
            .Where(type => type is { IsClass: true, IsAbstract: false } && type.GetInterfaces().Any(IsRequestHandler))
            .Select(type => type.Name)
            .ToList();

        var testClasses = typeof(ArchitectureTests).Assembly.GetTypes().Select(type => type.Name).ToHashSet();
        var missing = handlers.Where(handler => !testClasses.Contains(handler + "Tests")).OrderBy(name => name).ToList();

        Assert.That(handlers, Is.Not.Empty, "No handlers found; the check itself is broken.");
        Assert.That(missing, Is.Empty,
            "Handlers without a test class (expected <Handler>Tests in the unit test project): " + string.Join(", ", missing));
    }

    [Test]
    public void EveryEndpoint_RequiresAuthorization()
    {
        var programPath = Path.Combine(FindRepoRoot(), ApiProjectFolder, "Program.cs");
        var root = CSharpSyntaxTree.ParseText(File.ReadAllText(programPath)).GetRoot();

        var endpoints = root.DescendantNodes().OfType<InvocationExpressionSyntax>()
            .Where(invocation => invocation.Expression is MemberAccessExpressionSyntax
            {
                Expression: IdentifierNameSyntax { Identifier.Text: "app" }
            } member && EndpointMethods.Contains(member.Name.Identifier.Text))
            .ToList();

        var unprotected = endpoints
            .Where(endpoint => !MethodsChainedOnto(endpoint).Contains("RequireAuthorization"))
            .Select(Route)
            .Where(route => !PublicEndpoints.Contains(route))
            .ToList();

        // Route groups aren't covered yet; fail loudly rather than silently skip their endpoints
        var usesRouteGroups = root.DescendantNodes().OfType<MemberAccessExpressionSyntax>()
            .Any(access => access.Name.Identifier.Text == "MapGroup");
        Assert.That(usesRouteGroups, Is.False,
            "Program.cs uses MapGroup, which this check doesn't cover yet. Extend EveryEndpoint_RequiresAuthorization to handle route groups.");

        Assert.That(endpoints, Is.Not.Empty, "No endpoints found in Program.cs; the check itself is broken.");
        Assert.That(unprotected, Is.Empty,
            "Endpoints in Program.cs without .RequireAuthorization(): " + string.Join(", ", unprotected));
    }

    private static IEnumerable<Type> TypesInUseCase(string useCase) =>
        ApiAssembly.GetTypes().Where(type => !type.IsNested && type.Namespace != null &&
            (type.Namespace == $"{UseCasesNamespace}.{useCase}" || type.Namespace.StartsWith($"{UseCasesNamespace}.{useCase}.")));

    private static bool IsRequestHandler(Type type) =>
        type.IsGenericType &&
        (type.GetGenericTypeDefinition() == typeof(IRequestHandler<,>) ||
         type.GetGenericTypeDefinition() == typeof(IRequestHandler<>));

    private static string Route(InvocationExpressionSyntax endpoint) =>
        endpoint.ArgumentList.Arguments.FirstOrDefault()?.ToString().Trim('"') ?? "(unknown route)";

    private static IEnumerable<string> MethodsChainedOnto(InvocationExpressionSyntax invocation)
    {
        var current = invocation;
        while (current.Parent is MemberAccessExpressionSyntax access &&
               access.Parent is InvocationExpressionSyntax outer)
        {
            yield return access.Name.Identifier.Text;
            current = outer;
        }
    }

    private static string FindRepoRoot()
    {
        var directory = new DirectoryInfo(TestContext.CurrentContext.TestDirectory);
        while (directory != null && !File.Exists(Path.Combine(directory.FullName, SolutionFile)))
            directory = directory.Parent;

        return directory?.FullName ?? throw new InvalidOperationException($"Could not find {SolutionFile} above the test directory.");
    }
}
