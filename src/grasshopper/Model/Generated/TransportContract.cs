// Generated from the shared Speckle envelope contract.
namespace Rangekeeper.Serialization;
public static class TransportContract
{
    public const string Format = "rk.speckle-model/v1";
    public const string FormatField = "rk_format";
    public const string ModelField = "rk_model";
    public const string AssociationsField = "rk_associations";
    public static readonly string[] AssociationFields = new[] { "model_revision", "domain_id", "rhino_id", "application_id", "content_id" };
    public static readonly string[] RequiredAssociationFields = new[] { "model_revision", "domain_id" };
}
